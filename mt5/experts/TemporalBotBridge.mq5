#property strict
#property version   "1.00"
#property description "Bridge EA: sends market requests to Python bot and executes returned actions."

#include <Trade/Trade.mqh>
#include <stdlib.mqh>

input string InpBridgeFolder = "temporal_bot";
input string InpInterval = "1m";
input int    InpBars = 512;
input double InpVolume = 0.01;
input int    InpMaxSpreadPoints = 80;
input bool   InpAllowLiveOrders = false;
input int    InpMagic = 900001;
input bool   InpUseTrailing = true;
input int    InpTrailStartPoints = 120;
input int    InpTrailStepPoints = 60;

CTrade Trade;
datetime g_lastBar = 0;

string BuildPath(const string subfolder, const string file_name)
{
   string path = InpBridgeFolder + "\\" + subfolder;
   FolderCreate(path, FILE_COMMON);
   return path + "\\" + file_name;
}

string RequestId()
{
   return Symbol() + "_" + IntegerToString((int)Period()) + "_" + IntegerToString((int)TimeCurrent());
}

bool IsSpreadOk()
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(ask <= 0 || bid <= 0) return false;
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(point <= 0) return false;
   double spreadPts = (ask - bid) / point;
   return spreadPts <= InpMaxSpreadPoints;
}

void SendRequest()
{
   string reqId = RequestId();
   string fileName = reqId + ".json";
   string path = BuildPath("inbox", fileName);
   int h = FileOpen(path, FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      Print("[TemporalBotBridge] Failed to open request file: ", path);
      return;
   }

   string json = "{";
   json += "\"request_id\":\"" + reqId + "\",";
   json += "\"symbol\":\"" + _Symbol + "\",";
   json += "\"interval\":\"" + InpInterval + "\",";
   json += "\"bars\":" + IntegerToString(InpBars) + ",";
   json += "\"volume\":" + DoubleToString(InpVolume, 2) + ",";
   json += "\"time\":" + IntegerToString((int)TimeCurrent());
   json += "}";

   FileWriteString(h, json);
   FileClose(h);
}

string JsonValue(const string json, const string key)
{
   string tag = "\"" + key + "\":";
   int i = StringFind(json, tag);
   if(i < 0) return "";
   int start = i + StringLen(tag);
   while(start < StringLen(json) && (StringGetCharacter(json, start) == ' ')) start++;

   if(start < StringLen(json) && StringGetCharacter(json, start) == '"')
   {
      start++;
      int end = StringFind(json, "\"", start);
      if(end < 0) return "";
      return StringSubstr(json, start, end - start);
   }

   int end2 = start;
   while(end2 < StringLen(json))
   {
      ushort c = (ushort)StringGetCharacter(json, end2);
      if(c == ',' || c == '}') break;
      end2++;
   }
   return StringTrim(StringSubstr(json, start, end2 - start));
}

bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic)
      {
         return true;
      }
   }
   return false;
}

int CurrentPositionType()
{
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic)
      {
         return (int)PositionGetInteger(POSITION_TYPE);
      }
   }
   return -1;
}

void CloseBridgePositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic)
      {
         if(!Trade.PositionClose(ticket))
            Print("[TemporalBotBridge] PositionClose failed ticket=", ticket, " err=", GetLastError());
      }
   }
}

void UpdateTrailingStops()
{
   if(!InpAllowLiveOrders || !InpUseTrailing) return;
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(point <= 0) return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(bid <= 0 || ask <= 0) return;

   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      long pType = PositionGetInteger(POSITION_TYPE);
      double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      double curSL = PositionGetDouble(POSITION_SL);
      double curTP = PositionGetDouble(POSITION_TP);
      double trigger = InpTrailStartPoints * point;
      double step = InpTrailStepPoints * point;

      if(pType == POSITION_TYPE_BUY)
      {
         double profitDist = bid - openPrice;
         if(profitDist < trigger) continue;
         double nextSL = bid - step;
         if(curSL <= 0 || nextSL > curSL + point)
         {
            if(!Trade.PositionModify(ticket, nextSL, curTP))
               Print("[TemporalBotBridge] Trailing BUY modify failed ticket=", ticket, " err=", GetLastError());
         }
      }
      else if(pType == POSITION_TYPE_SELL)
      {
         double profitDist = openPrice - ask;
         if(profitDist < trigger) continue;
         double nextSL = ask + step;
         if(curSL <= 0 || nextSL < curSL - point)
         {
            if(!Trade.PositionModify(ticket, nextSL, curTP))
               Print("[TemporalBotBridge] Trailing SELL modify failed ticket=", ticket, " err=", GetLastError());
         }
      }
   }
}

void ExecuteDecision(const string action, double sl, double tp, double volume)
{
   if(!InpAllowLiveOrders)
   {
      Print("[TemporalBotBridge] Dry mode action=", action);
      return;
   }

   if(!IsSpreadOk())
   {
      Print("[TemporalBotBridge] Spread too high, skip.");
      return;
   }

   Trade.SetExpertMagicNumber(InpMagic);

   if(action == "buy")
   {
      int pType = CurrentPositionType();
      if(pType == POSITION_TYPE_BUY) return;
      if(pType == POSITION_TYPE_SELL) CloseBridgePositions();
      if(!Trade.Buy(volume, _Symbol, 0.0, sl, tp, "temporal_bridge_buy"))
         Print("[TemporalBotBridge] Buy failed: ", GetLastError());
   }
   else if(action == "sell")
   {
      int pType = CurrentPositionType();
      if(pType == POSITION_TYPE_SELL) return;
      if(pType == POSITION_TYPE_BUY) CloseBridgePositions();
      if(!Trade.Sell(volume, _Symbol, 0.0, sl, tp, "temporal_bridge_sell"))
         Print("[TemporalBotBridge] Sell failed: ", GetLastError());
   }
   else if(action == "close")
   {
      CloseBridgePositions();
   }
}

void PollDecision()
{
   string reqId = Symbol() + "_" + IntegerToString((int)Period()) + "_" + IntegerToString((int)g_lastBar);
   string path = BuildPath("outbox", reqId + ".json");

   if(!FileIsExist(path, FILE_COMMON)) return;

   int h = FileOpen(path, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(h == INVALID_HANDLE)
   {
      Print("[TemporalBotBridge] Failed to read decision file: ", path);
      return;
   }
   string json = FileReadString(h);
   FileClose(h);

   string action = StringToLower(JsonValue(json, "action"));
   double sl = StringToDouble(JsonValue(json, "sl"));
   double tp = StringToDouble(JsonValue(json, "tp"));
   double volume = StringToDouble(JsonValue(json, "volume"));
   if(volume <= 0) volume = InpVolume;

   ExecuteDecision(action, sl, tp, volume);
   FileDelete(path, FILE_COMMON);
}

int OnInit()
{
   FolderCreate(InpBridgeFolder, FILE_COMMON);
   FolderCreate(InpBridgeFolder + "\\inbox", FILE_COMMON);
   FolderCreate(InpBridgeFolder + "\\outbox", FILE_COMMON);
   Print("[TemporalBotBridge] Ready. allowLive=", InpAllowLiveOrders ? "true" : "false");
   return(INIT_SUCCEEDED);
}

void OnTick()
{
   UpdateTrailingStops();
   datetime curBar = iTime(_Symbol, _Period, 0);
   if(curBar != g_lastBar)
   {
      g_lastBar = curBar;
      SendRequest();
   }
   PollDecision();
}
