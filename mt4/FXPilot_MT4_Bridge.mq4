#property strict
#property version "2.00"
#property description "FXPilot: 4 symbols and 5 timeframes from one MT4 chart"

input string ServerUrl = "https://fxpilot-orderflow-engine.onrender.com/api/mt4/batch";
input string ApiToken = "";
input string BrokerSymbolsCsv = "EURUSD,GBPUSD,USDJPY,XAUUSD";
input int BarsToSend = 10;
input int SendEverySeconds = 60;
input bool SendOnStart = true;
input int HttpTimeoutMs = 10000;

#define SYMBOL_COUNT 4
#define TF_COUNT 5
#define BTN_NAME "FXPILOT_SEND_NOW"

string CanonicalSymbols[SYMBOL_COUNT] = {"EURUSD","GBPUSD","USDJPY","XAUUSD"};
string BrokerSymbols[SYMBOL_COUNT];
int Timeframes[TF_COUNT] = {PERIOD_M15,PERIOD_H1,PERIOD_H4,PERIOD_D1,PERIOD_W1};
long Samples[SYMBOL_COUNT], UpTicks[SYMBOL_COUNT], DownTicks[SYMBOL_COUNT], FlatTicks[SYMBOL_COUNT];
double LastBid[SYMBOL_COUNT], SpreadSum[SYMBOL_COUNT], SpreadMax[SYMBOL_COUNT];
datetime LastSendAt=0;
string LastStatus="Starting";
int OkPackets=0, FailedPackets=0;

string Trim(string value){ StringTrimLeft(value); StringTrimRight(value); return value; }
string TfName(int tf){ if(tf==PERIOD_M15)return "M15"; if(tf==PERIOD_H1)return "H1"; if(tf==PERIOD_H4)return "H4"; if(tf==PERIOD_D1)return "D1"; return "W1"; }
string Num(double value,int digits){ return DoubleToString(value,digits); }
string JsonEscape(string value){ StringReplace(value,"\\","\\\\"); StringReplace(value,"\"","\\\""); return value; }

void ResetStats(int i){ Samples[i]=0; UpTicks[i]=0; DownTicks[i]=0; FlatTicks[i]=0; SpreadSum[i]=0; SpreadMax[i]=0; }

void SampleSymbols(){
   for(int i=0;i<SYMBOL_COUNT;i++){
      string s=BrokerSymbols[i];
      double bid=MarketInfo(s,MODE_BID), ask=MarketInfo(s,MODE_ASK), point=MarketInfo(s,MODE_POINT);
      if(bid<=0 || ask<=0 || point<=0) continue;
      if(LastBid[i]>0){ if(bid>LastBid[i])UpTicks[i]++; else if(bid<LastBid[i])DownTicks[i]++; else FlatTicks[i]++; }
      LastBid[i]=bid; double spread=(ask-bid)/point; Samples[i]++; SpreadSum[i]+=spread; if(spread>SpreadMax[i])SpreadMax[i]=spread;
   }
}

string BuildCandles(string symbol,int tf){
   string out="["; int digits=(int)MarketInfo(symbol,MODE_DIGITS); int count=MathMin(BarsToSend,iBars(symbol,tf)); bool first=true;
   for(int shift=count-1;shift>=0;shift--){
      datetime t=iTime(symbol,tf,shift); if(t<=0)continue; if(!first)out+=","; first=false;
      out+="{\"time\":"+IntegerToString((int)t);
      out+=",\"open\":"+Num(iOpen(symbol,tf,shift),digits);
      out+=",\"high\":"+Num(iHigh(symbol,tf,shift),digits);
      out+=",\"low\":"+Num(iLow(symbol,tf,shift),digits);
      out+=",\"close\":"+Num(iClose(symbol,tf,shift),digits);
      out+=",\"tick_volume\":"+IntegerToString((int)iVolume(symbol,tf,shift))+"}";
   }
   return out+"]";
}

string BuildPayload(int i,int tf){
   string s=BrokerSymbols[i]; int digits=(int)MarketInfo(s,MODE_DIGITS); double avg=Samples[i]>0?SpreadSum[i]/Samples[i]:0;
   string p="{\"schema_version\":\"2.0\",\"source\":\"mt4\"";
   p+=",\"symbol\":\""+CanonicalSymbols[i]+"\",\"broker_symbol\":\""+JsonEscape(s)+"\"";
   p+=",\"timeframe\":\""+TfName(tf)+"\",\"sent_at\":"+IntegerToString((int)TimeCurrent());
   p+=",\"broker\":\""+JsonEscape(AccountCompany())+"\",\"account\":\""+IntegerToString(AccountNumber())+"\"";
   p+=",\"candles\":"+BuildCandles(s,tf)+",\"ticks\":{";
   p+="\"samples\":"+IntegerToString((int)Samples[i])+",\"up_ticks\":"+IntegerToString((int)UpTicks[i]);
   p+=",\"down_ticks\":"+IntegerToString((int)DownTicks[i])+",\"unchanged_ticks\":"+IntegerToString((int)FlatTicks[i]);
   p+=",\"delta\":"+IntegerToString((int)(UpTicks[i]-DownTicks[i]))+",\"spread_avg_points\":"+Num(avg,1);
   p+=",\"spread_max_points\":"+Num(SpreadMax[i],1)+",\"last_bid\":"+Num(MarketInfo(s,MODE_BID),digits);
   p+=",\"last_ask\":"+Num(MarketInfo(s,MODE_ASK),digits)+"}}";
   return p;
}

bool PostJson(string payload){
   char data[],response[]; string responseHeaders; StringToCharArray(payload,data,0,WHOLE_ARRAY,CP_UTF8); ArrayResize(data,ArraySize(data)-1);
   string headers="Content-Type: application/json\r\nX-FXPilot-MT4-Token: "+ApiToken+"\r\n";
   ResetLastError(); int code=WebRequest("POST",ServerUrl,headers,HttpTimeoutMs,data,response,responseHeaders);
   if(code==-1){LastStatus="WebRequest error "+IntegerToString(GetLastError());return false;}
   if(code<200 || code>=300){LastStatus="Server HTTP "+IntegerToString(code);return false;}
   return true;
}

void UpdatePanel(){
   string next=LastSendAt>0?TimeToString(LastSendAt+SendEverySeconds,TIME_SECONDS):"now";
   Comment("FXPilot MT4 Bridge v2\n4 symbols | M15 H1 H4 D1 W1\n",LastStatus,"\nPackets OK/failed: ",OkPackets,"/",FailedPackets,"\nNext: ",next);
}

void SendAll(){
   if(StringLen(ApiToken)==0){LastStatus="Set ApiToken in EA settings";UpdatePanel();return;}
   int ok=0,failed=0; LastStatus="Sending...";UpdatePanel();
   for(int i=0;i<SYMBOL_COUNT;i++)for(int t=0;t<TF_COUNT;t++){ if(PostJson(BuildPayload(i,Timeframes[t]))){ok++;OkPackets++;}else{failed++;FailedPackets++;} }
   LastSendAt=TimeCurrent(); LastStatus="Cycle OK "+IntegerToString(ok)+", failed "+IntegerToString(failed);
   for(int s=0;s<SYMBOL_COUNT;s++)ResetStats(s); UpdatePanel();
}

void CreateButton(){ ObjectDelete(0,BTN_NAME); ObjectCreate(0,BTN_NAME,OBJ_BUTTON,0,0,0); ObjectSetInteger(0,BTN_NAME,OBJPROP_CORNER,CORNER_RIGHT_UPPER); ObjectSetInteger(0,BTN_NAME,OBJPROP_XDISTANCE,12); ObjectSetInteger(0,BTN_NAME,OBJPROP_YDISTANCE,18); ObjectSetInteger(0,BTN_NAME,OBJPROP_XSIZE,140); ObjectSetInteger(0,BTN_NAME,OBJPROP_YSIZE,24); ObjectSetString(0,BTN_NAME,OBJPROP_TEXT,"Send FXPilot now"); }

int OnInit(){
   string parsed[]; int count=StringSplit(BrokerSymbolsCsv,',',parsed); if(count!=SYMBOL_COUNT){Print("FXPilot: BrokerSymbolsCsv must contain exactly 4 symbols");return INIT_PARAMETERS_INCORRECT;}
   for(int i=0;i<SYMBOL_COUNT;i++){BrokerSymbols[i]=Trim(parsed[i]);if(!SymbolSelect(BrokerSymbols[i],true))Print("FXPilot: check broker symbol ",BrokerSymbols[i]);ResetStats(i);}
   EventSetTimer(1);CreateButton();SampleSymbols();LastStatus="Ready";UpdatePanel();if(SendOnStart)SendAll();return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){EventKillTimer();ObjectDelete(0,BTN_NAME);Comment("");}
void OnTimer(){SampleSymbols();if(LastSendAt==0 || TimeCurrent()-LastSendAt>=SendEverySeconds)SendAll();else UpdatePanel();}
void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam){if(id==CHARTEVENT_OBJECT_CLICK && sparam==BTN_NAME){ObjectSetInteger(0,BTN_NAME,OBJPROP_STATE,false);SendAll();}}
