//+------------------------------------------------------------------+
//| ZentinelBridge.mq5                                                |
//| Service (background, no chart needed) that answers on-demand     |
//| OHLCV requests from the local Python bridge for ChartZentinel.   |
//|                                                                    |
//| Protocol (files inside Common\Files\zentinel\, FILE_COMMON):     |
//|   request.txt   -> written by bridge_server.py:                  |
//|       id=<ms timestamp>                                          |
//|       symbol=<MT5 symbol name>                                   |
//|       interval=<1min|3min|5min|15min|30min|1h|2h|4h|1day|1week|1month> |
//|       bars=<int>                                                 |
//|   resp_<id>.txt -> written by this service:                      |
//|       JSON array [{"time":...,"open":...,...}] or {"error":"…"}  |
//|                                                                    |
//| Time values are shifted -7h from broker/server time so the JSON  |
//| carries New York time as plain epoch seconds (verified fixed      |
//| broker offset: broker_time = NY_time + 7h, year-round).           |
//+------------------------------------------------------------------+
#property service
#property strict

#define ZDIR "zentinel/"
#define BROKER_TO_NY_SECONDS (7*3600)

//--- ENUM_TIMEFRAMES mapping for the strings ChartZentinel's tf-bar uses
ENUM_TIMEFRAMES MapInterval(const string s)
{
   if(s=="1min")  return PERIOD_M1;
   if(s=="2min")  return PERIOD_M2;
   if(s=="3min")  return PERIOD_M3;
   if(s=="4min")  return PERIOD_M4;
   if(s=="5min")  return PERIOD_M5;
   if(s=="6min")  return PERIOD_M6;
   if(s=="10min") return PERIOD_M10;
   if(s=="12min") return PERIOD_M12;
   if(s=="15min") return PERIOD_M15;
   if(s=="20min") return PERIOD_M20;
   if(s=="30min") return PERIOD_M30;
   if(s=="1h")    return PERIOD_H1;
   if(s=="2h")    return PERIOD_H2;
   if(s=="3h")    return PERIOD_H3;
   if(s=="4h")    return PERIOD_H4;
   if(s=="6h")    return PERIOD_H6;
   if(s=="8h")    return PERIOD_H8;
   if(s=="12h")   return PERIOD_H12;
   if(s=="1day")  return PERIOD_D1;
   if(s=="1week") return PERIOD_W1;
   if(s=="1month")return PERIOD_MN1;
   return PERIOD_CURRENT;
}

//--- read whole text file (FILE_COMMON) into a string
bool ReadCommonFile(const string name, string &out)
{
   int h = FileOpen(name, FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(h==INVALID_HANDLE) return false;
   out="";
   while(!FileIsEnding(h))
      out += FileReadString(h) + "\n";
   FileClose(h);
   return true;
}

bool WriteCommonFile(const string name, const string content)
{
   int h = FileOpen(name, FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(h==INVALID_HANDLE) return false;
   FileWriteString(h, content);
   FileClose(h);
   return true;
}

//--- very small key=value line parser
string KeyValue(const string &lines[], int n, const string key)
{
   for(int i=0;i<n;i++)
   {
      int pos = StringFind(lines[i], "=");
      if(pos<=0) continue;
      string k = StringSubstr(lines[i],0,pos);
      if(k==key) return StringSubstr(lines[i],pos+1);
   }
   return "";
}

void WriteSymbolsList()
{
   int total = SymbolsTotal(false);
   string json = "[";
   for(int i=0;i<total;i++)
   {
      if(i>0) json += ",";
      json += "\"" + SymbolName(i,false) + "\"";
   }
   json += "]";
   WriteCommonFile(ZDIR+"symbols.json", json);
}

void HandleRequest()
{
   string raw;
   if(!ReadCommonFile(ZDIR+"request.txt", raw)) return;

   string lines[];
   int n = StringSplit(raw, '\n', lines);

   string id      = KeyValue(lines,n,"id");
   string symbol  = KeyValue(lines,n,"symbol");
   string interval= KeyValue(lines,n,"interval");
   string barsStr = KeyValue(lines,n,"bars");
   string beforeStr = KeyValue(lines,n,"before");
   int bars = (int)StringToInteger(barsStr);
   if(bars<=0) bars=500;

   // request consumed either way
   FileDelete(ZDIR+"request.txt", FILE_COMMON);
   if(id=="") return;

   string respFile = ZDIR+"resp_"+id+".txt";

   if(symbol=="" || !SymbolSelect(symbol, true))
   {
      WriteCommonFile(respFile, "{\"error\":\"symbol not found: "+symbol+"\"}");
      return;
   }

   ENUM_TIMEFRAMES tf = MapInterval(interval);
   if(tf==PERIOD_CURRENT)
   {
      WriteCommonFile(respFile, "{\"error\":\"unknown interval: "+interval+"\"}");
      return;
   }

   // "before" (scroll infinito hacia atrás): pedir `bars` velas más viejas
   // que ese momento, en vez de las más recientes. Se traduce a un índice
   // de posición (shift) porque es más confiable que el overload por fecha.
   int startShift = 0;
   if(beforeStr != "")
   {
      long beforeNy = StringToInteger(beforeStr);
      datetime beforeBroker = (datetime)(beforeNy + BROKER_TO_NY_SECONDS);
      startShift = iBarShift(symbol, tf, beforeBroker, false) + 1;
      if(startShift < 0) startShift = 0;
   }

   // Si MT5 todavía no tiene esas velas en caché local (pasa seguido en
   // timeframes que nunca abriste como chart en la terminal), la primera
   // CopyRates() devuelve menos de lo pedido mientras dispara la descarga
   // en segundo plano. Reintentamos un rato para darle tiempo a completarla
   // en vez de devolver un historial corto silenciosamente.
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(symbol, tf, startShift, bars, rates);
   for(int attempt=0; attempt<15 && copied<bars; attempt++)
   {
      Sleep(300);
      copied = CopyRates(symbol, tf, startShift, bars, rates);
   }
   if(copied<=0)
   {
      WriteCommonFile(respFile, "{\"error\":\"no data for "+symbol+" ("+IntegerToString(copied)+")\"}");
      return;
   }

   string bars_json = "[";
   // rates[] comes newest-first (series); emit oldest-first for the chart
   for(int i=copied-1; i>=0; i--)
   {
      long nyTime = (long)rates[i].time - BROKER_TO_NY_SECONDS;
      if(i<copied-1) bars_json += ",";
      bars_json += StringFormat(
         "{\"time\":%I64d,\"open\":%.5f,\"high\":%.5f,\"low\":%.5f,\"close\":%.5f,\"volume\":%I64d}",
         nyTime, rates[i].open, rates[i].high, rates[i].low, rates[i].close, rates[i].tick_volume);
   }
   bars_json += "]";

   long serverNyTime = (long)TimeCurrent() - BROKER_TO_NY_SECONDS;
   string json = StringFormat("{\"serverTime\":%I64d,\"bars\":%s}", serverNyTime, bars_json);
   WriteCommonFile(respFile, json);
}

void OnStart()
{
   FolderCreate(ZDIR, FILE_COMMON);
   WriteSymbolsList();

   ulong lastSymbolsRefresh = GetTickCount64();

   while(!IsStopped())
   {
      if(FileIsExist(ZDIR+"request.txt", FILE_COMMON))
         HandleRequest();

      if(GetTickCount64() - lastSymbolsRefresh > 5*60*1000)
      {
         WriteSymbolsList();
         lastSymbolsRefresh = GetTickCount64();
      }

      Sleep(200);
   }
}
