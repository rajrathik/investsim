const API="http://localhost:8000/api";
const AMTS=[500,1000,2000,5000],YRS=[3,5,7,10,15,20];
const MO=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
let allTickers=[],selected=[],alloc={},selAmt=1000,selYr=10;
let snapshots=null,breakdownData=null;

/* Column info tooltips — shown on hover of the * icon in table headers */
const COL_INFO={
  invested:'Monthly amount allocated per your % split. Bought at the monthly high price (worst-case entry).',
  shares:'Shares purchased = $ invested ÷ monthly high price. Click to see per-ticker breakdown.',
  dividends:'Cash dividends received based on shares held × dividend per share. Not reinvested.',
  divvalue:'Accumulated dividends invested in money market. Each month\'s balance grows at the federal funds rate ÷ 12.',
  portfolio:'Total shares held × monthly close price for each ticker, summed across all holdings.'
};
let mmRates={}; /* key: "YYYY-MM" → annual rate as decimal e.g. 0.05 */

function $(id){return document.getElementById(id)}
function fmt(n){return(n||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}
function fmtS(n){if(n>=1e6)return'$'+(n/1e6).toFixed(2)+'M';if(n>=1e3)return'$'+(n/1e3).toFixed(1)+'K';return'$'+fmt(n)}
function tot(){return selected.reduce((a,s)=>a+(alloc[s]||0),0)}
function getTk(s){return allTickers.find(t=>t.symbol===s)}

/* Helper to build a column header with * tooltip */
function thWithInfo(label,key){
  return '<th>'+label+'<span class="col-info">*<span class="col-tooltip">'+COL_INFO[key]+'</span></span></th>';
}

function renderAmts(){$('amtBtns').innerHTML=AMTS.map(v=>'<button class="btn f1 '+(selAmt===v?'on':'')+'" onclick="setAmt('+v+')">$'+v.toLocaleString()+'</button>').join('')}
function setAmt(v){selAmt=v;$('amt').value=v;renderAmts()}
$('amt').addEventListener('input',function(){selAmt=Math.max(0,parseInt(this.value)||0);renderAmts()});
function renderYrs(){$('yrBtns').innerHTML=YRS.map(y=>'<button class="btn '+(selYr===y?'on':'')+'" onclick="setYr('+y+')">'+y+'Y</button>').join('')}
function setYr(y){selYr=y;$('yrInp').value=y;renderYrs()}
$('yrInp').addEventListener('input',function(){selYr=Math.max(1,Math.min(20,parseInt(this.value)||1));renderYrs()});

const si=$('searchInp'),dd=$('dropdown');
function showDD(q){
  q=(q||'').toLowerCase().trim();
  let list=q?allTickers.filter(t=>t.symbol.toLowerCase().includes(q)||(t.name||'').toLowerCase().includes(q)):allTickers;
  if(!list.length){dd.innerHTML='<div style="padding:14px;color:var(--text3);text-align:center">No matches</div>';dd.classList.add('show');return}
  dd.innerHTML=list.map(t=>{const sel=selected.includes(t.symbol);return'<div class="dd-item" onclick="togTk(\''+t.symbol+'\')"><div><span class="dd-sym">'+t.symbol+'</span><span class="dd-name">'+(t.name||'')+'</span></div>'+(sel?'<span class="dd-check">✓</span>':'')+'</div>'}).join('');
  dd.classList.add('show');
}
si.addEventListener('input',function(){showDD(this.value)});
si.addEventListener('focus',function(){showDD(this.value)});
si.addEventListener('click',function(){showDD(this.value)});
document.addEventListener('click',function(e){if(!e.target.closest('.search-wrap'))dd.classList.remove('show')});
function togTk(s){if(selected.includes(s)){selected=selected.filter(x=>x!==s);delete alloc[s]}else{selected.push(s);alloc[s]=0}renderChips();renderAlloc();updBudget();showDD(si.value);si.focus()}
function remTk(s){selected=selected.filter(x=>x!==s);delete alloc[s];renderChips();renderAlloc();updBudget()}
function renderChips(){$('chips').innerHTML=selected.map(s=>{const t=getTk(s);return'<div class="chip">'+s+' <span style="opacity:.6;font-weight:400">'+(t?.name||'')+'</span> <span class="x" onclick="remTk(\''+s+'\')">✕</span></div>'}).join('')}

function updBudget(){
  const t=tot(),bar=$('budgetBar'),btn=$('runBtn');let bg,c,txt;
  if(!selected.length){bg='var(--border)';c='var(--text3)';txt='Select tickers above to begin'}
  else if(t===100){bg='var(--accent-dim)';c='var(--accent)';txt='✓ Fully allocated'}
  else if(t>100){bg='var(--red-dim)';c='var(--red)';txt='Over allocated! Reduce to 100%'}
  else{bg='var(--gold-dim)';c='var(--gold)';txt=(100-t)+'% remaining'}
  bar.style.background=bg;bar.innerHTML='<span style="font-size:13px;font-weight:600;color:'+c+'">'+txt+'</span><span style="font-size:22px;font-weight:700;color:'+(t===100?'var(--accent)':t>100?'var(--red)':'var(--text1)')+'">'+t+'%</span>';
  const ok=t===100&&selected.length>0&&selAmt>0;btn.disabled=!ok;
  btn.style.background=ok?'linear-gradient(135deg,var(--accent),#059669)':'var(--border)';btn.style.color=ok?'#fff':'var(--text3)';btn.style.boxShadow=ok?'0 4px 24px var(--accent-glow)':'none';
}
function renderAlloc(){
  if(!selected.length){$('allocList').innerHTML='<div class="empty-state"><div class="em-icon">🎯</div>Click the search box above to browse<br>all available tickers and select them</div>';return}
  $('allocList').innerHTML=selected.map(s=>{const t=getTk(s),p=alloc[s]||0;return'<div class="ar"><div style="min-width:90px"><div class="sym">'+s+'</div><div class="nm">'+(t?.name||'')+'</div></div><div style="flex:1"><input type="range" min="0" max="100" step="1" value="'+p+'" oninput="setA(\''+s+'\',+this.value)"></div><div class="pct">'+p+'%</div></div>'}).join('');
}
function setA(s,v){alloc[s]=v;renderAlloc();updBudget()}
function resetA(){selected=[];alloc={};si.value='';dd.classList.remove('show');snapshots=null;breakdownData=null;renderChips();renderAlloc();updBudget();$('results').innerHTML=''}
function eqSplit(){if(!selected.length)return;const n=selected.length,base=Math.floor(100/n),rem=100-base*n;selected.forEach((s,i)=>alloc[s]=base+(i<rem?1:0));renderAlloc();updBudget()}

function openModal(idx,context){$('modalOverlay').classList.add('show');if(idx===undefined)renderPortfolioModal();else if(context)renderContextModal(idx,context);else renderMonthModal(idx)}
function closeModal(){$('modalOverlay').classList.remove('show')}

function renderPortfolioModal(){
  if(!snapshots||!snapshots.length){$('modalBody').innerHTML='<p style="color:var(--text3)">No data</p>';return}
  const snap=snapshots[snapshots.length-1];
  $('modalTitle').textContent='Portfolio Breakdown';
  $('modalSub').textContent='Final snapshot as of last available month';
  let h='',tv=0;const syms=Object.keys(snap.tickers);
  syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);tv+=d.value;
    h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val">$'+fmt(d.value)+'</div><div class="d-sub">'+d.totalShares.toFixed(4)+' shares × $'+fmt(d.closePrice)+' close</div><div class="d-sub2">'+d.origPct+'% target alloc · Divs earned: $'+fmt(d.totalDivs)+'</div></div></div>'});
  h+='<div class="detail-total"><div><div class="dt-label">Total Portfolio Value</div><div style="font-size:12px;color:var(--text2);margin-top:2px">'+syms.length+' holdings</div></div><div class="dt-val">$'+fmt(tv)+'</div></div>';
  $('modalBody').innerHTML=h;
}

function renderMonthModal(idx){
  const snap=snapshots[idx],bk=breakdownData[idx];
  $('modalTitle').textContent=MO[bk.month-1]+' '+bk.year+' — Month Detail';
  const wasRedist=snap.redistributed;
  $('modalSub').textContent='Snapshot of your portfolio at end of this month'+(wasRedist?' · Allocation was redistributed this month':'');
  let h='';
  h+='<div class="section-label">Shares Purchased This Month</div>';
  const syms=Object.keys(snap.tickers);
  syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);
    if(d.boughtThisMonth>0){
      let note='';
      if(d.effectivePct!==d.origPct)note='<div class="redist-note">Redistributed: '+d.origPct+'% → '+d.effectivePct.toFixed(1)+'% effective</div>';
      h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val">+'+d.boughtThisMonth.toFixed(4)+' shares</div><div class="d-sub">$'+fmt(d.investedThisMonth)+' invested at $'+fmt(d.buyPrice)+' high</div>'+note+'</div></div>'
    } else if(d.origPct>0){
      h+='<div class="detail-row" style="opacity:.5"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--text3)">No data</div><div class="d-sub">Allocation redistributed to other tickers</div></div></div>'
    }
  });
  const anyDiv=syms.some(s=>snap.tickers[s].divsThisMonth>0);
  if(anyDiv){
    h+='<div class="section-label">Dividends This Month</div>';
    syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);
      if(d.divsThisMonth>0)h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--gold)">$'+fmt(d.divsThisMonth)+'</div><div class="d-sub">on '+d.totalShares.toFixed(4)+' shares held</div></div></div>'});
  }
  h+='<div class="section-label">Running Portfolio Totals</div>';
  let tv=0;
  syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);tv+=d.value;
    h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val">$'+fmt(d.value)+'</div><div class="d-sub">'+d.totalShares.toFixed(4)+' total shares × $'+fmt(d.closePrice)+' close</div><div class="d-sub2">Total divs to date: $'+fmt(d.totalDivs)+'</div></div></div>'});
  h+='<div class="detail-total"><div><div class="dt-label">Portfolio Value</div><div style="font-size:12px;color:var(--text2);margin-top:2px">Total invested: $'+fmt(bk.tInv)+' · Total divs: $'+fmt(bk.tDiv)+'</div></div><div class="dt-val">$'+fmt(bk.pv)+'</div></div>';
  $('modalBody').innerHTML=h;
}

function renderContextModal(idx,context){
  const snap=snapshots[idx],bk=breakdownData[idx];
  const monthLabel=MO[bk.month-1]+' '+bk.year;
  const syms=Object.keys(snap.tickers);
  let h='';

  if(context==='invested'){
    $('modalTitle').textContent=monthLabel+' — Investment Split';
    $('modalSub').textContent='How $'+fmt(bk.invested)+' was allocated across tickers';
    let totalInv=0;
    syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);
      if(d.investedThisMonth>0){totalInv+=d.investedThisMonth;
        let note='';if(d.effectivePct!==d.origPct)note='<div class="redist-note" style="font-size:10px;padding:3px 8px;margin-top:1px">'+d.origPct+'% → '+d.effectivePct.toFixed(1)+'%</div>';
        h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val">$'+fmt(d.investedThisMonth)+'</div><div class="d-sub">at $'+fmt(d.buyPrice)+' high</div>'+note+'</div></div>'}
      else if(d.origPct>0){h+='<div class="detail-row" style="opacity:.4"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--text3);font-size:13px">No data</div></div></div>'}
    });
    h+='<div class="detail-total"><div class="dt-label">Total Invested</div><div class="dt-val">$'+fmt(totalInv)+'</div></div>';
  }

  else if(context==='shares'){
    $('modalTitle').textContent=monthLabel+' — Shares Purchased';
    $('modalSub').textContent='New shares acquired this month';
    let totalShares=0;
    syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);
      if(d.boughtThisMonth>0){totalShares+=d.boughtThisMonth;
        h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val">+'+d.boughtThisMonth.toFixed(4)+'</div><div class="d-sub">$'+fmt(d.investedThisMonth)+' ÷ $'+fmt(d.buyPrice)+'</div></div></div>'}
      else if(d.origPct>0){h+='<div class="detail-row" style="opacity:.4"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--text3);font-size:13px">No data</div></div></div>'}
    });
    h+='<div class="detail-total"><div class="dt-label">Total Shares Bought</div><div class="dt-val">'+totalShares.toFixed(4)+'</div></div>';
  }

  else if(context==='dividends'){
    $('modalTitle').textContent=monthLabel+' — Dividends Received';
    const anyDiv=syms.some(s=>snap.tickers[s].divsThisMonth>0);
    if(!anyDiv){$('modalSub').textContent='No dividends were paid this month';h='<div style="text-align:center;padding:20px;color:var(--text3)">No dividends this month</div>';}
    else{
      $('modalSub').textContent='Dividend income from each holding';
      let totalDiv=0;
      syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);
        if(d.divsThisMonth>0){totalDiv+=d.divsThisMonth;
          h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--gold)">$'+fmt(d.divsThisMonth)+'</div><div class="d-sub">on '+d.totalShares.toFixed(2)+' shares</div></div></div>'}
      });
      h+='<div class="detail-total" style="background:var(--gold-dim);border-color:rgba(245,158,11,.25)"><div class="dt-label" style="color:var(--gold)">Total Dividends</div><div class="dt-val" style="color:var(--gold)">$'+fmt(totalDiv)+'</div></div>';
    }
  }

  else if(context==='portfolio'){
    $('modalTitle').textContent=monthLabel+' — Portfolio Value';
    $('modalSub').textContent='Value split across holdings';
    let tv=0;
    syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);tv+=d.value;
      h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--accent)">$'+fmt(d.value)+'</div><div class="d-sub">'+d.totalShares.toFixed(2)+' × $'+fmt(d.closePrice)+'</div></div></div>'});
    h+='<div class="detail-total"><div><div class="dt-label">Total Value</div><div style="font-size:11px;color:var(--text2);margin-top:1px">Invested: $'+fmt(bk.tInv)+' · Divs: $'+fmt(bk.tDiv)+'</div></div><div class="dt-val">$'+fmt(tv)+'</div></div>';
  }

  $('modalBody').innerHTML=h;
}

/* Summary card: Dividends Earned — per-ticker accumulated dividends */
function showDivSummary(){
  if(!snapshots||!snapshots.length)return;
  const snap=snapshots[snapshots.length-1];
  $('modalTitle').textContent='Dividends Earned — By Security';
  $('modalSub').textContent='Total dividends accumulated over the full period';
  const syms=Object.keys(snap.tickers);
  let h='',totalDiv=0;
  syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);totalDiv+=d.totalDivs;
    h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--gold)">$'+fmt(d.totalDivs)+'</div><div class="d-sub">'+d.totalShares.toFixed(2)+' shares held</div></div></div>'});
  h+='<div class="detail-total" style="background:var(--gold-dim);border-color:rgba(245,158,11,.25)"><div class="dt-label" style="color:var(--gold)">Total Dividends</div><div class="dt-val" style="color:var(--gold)">$'+fmt(totalDiv)+'</div></div>';
  $('modalBody').innerHTML=h;
  $('modalOverlay').classList.add('show');
}

/* Summary card: Div + MM Interest — shows dividends earned vs current value with interest */
function showDivValueSummary(){
  if(!snapshots||!snapshots.length||!window._lastResults)return;
  const r=window._lastResults;
  $('modalTitle').textContent='Dividends + Money Market Interest';
  $('modalSub').textContent='Dividends invested at monthly federal funds rate';
  let h='';
  h+='<div class="detail-row"><div><div class="d-sym" style="color:var(--gold)">Dividends Earned</div><div class="d-name">Total cash received from all holdings</div></div><div class="d-nums"><div class="d-val" style="color:var(--gold)">$'+fmt(r.tDiv)+'</div></div></div>';
  h+='<div class="detail-row"><div><div class="d-sym" style="color:var(--accent)">MM Interest Earned</div><div class="d-name">Growth from money market rate</div></div><div class="d-nums"><div class="d-val" style="color:var(--accent)">$'+fmt(r.divBal-r.tDiv)+'</div></div></div>';
  h+='<div class="detail-total" style="background:var(--gold-dim);border-color:rgba(245,158,11,.25)"><div><div class="dt-label" style="color:var(--gold)">Current Dividend Value</div><div style="font-size:11px;color:var(--text2);margin-top:1px">Dividends + accumulated interest</div></div><div class="dt-val" style="color:var(--gold)">$'+fmt(r.divBal)+'</div></div>';
  $('modalBody').innerHTML=h;
  $('modalOverlay').classList.add('show');
}

/* Summary card: Total Value + Dividends — portfolio value + cash breakdown */
function showTotalSummary(){
  if(!snapshots||!snapshots.length||!window._lastResults)return;
  const snap=snapshots[snapshots.length-1],r=window._lastResults;
  $('modalTitle').textContent='Total Return Breakdown';
  $('modalSub').textContent='Portfolio holdings value + accumulated dividends';
  const syms=Object.keys(snap.tickers);
  let h='',tv=0,td=0;
  h+='<div class="section-label">Holdings Value (shares × close)</div>';
  syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);tv+=d.value;
    h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--accent)">$'+fmt(d.value)+'</div><div class="d-sub">'+d.totalShares.toFixed(2)+' × $'+fmt(d.closePrice)+'</div></div></div>'});
  h+='<div class="detail-total"><div class="dt-label">Holdings Subtotal</div><div class="dt-val">$'+fmt(tv)+'</div></div>';
  h+='<div class="section-label" style="margin-top:16px">Dividends + MM Interest</div>';
  syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);td+=d.totalDivs;
    if(d.totalDivs>0)h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--gold)">$'+fmt(d.totalDivs)+'</div></div></div>'});
  const mmInt=r.divBal-r.tDiv;
  h+='<div class="detail-row"><div><div class="d-sym" style="color:var(--accent)">MM Interest</div><div class="d-name">Earned on dividend balance</div></div><div class="d-nums"><div class="d-val" style="color:var(--accent)">$'+fmt(mmInt)+'</div></div></div>';
  h+='<div class="detail-total" style="background:var(--gold-dim);border-color:rgba(245,158,11,.25)"><div class="dt-label" style="color:var(--gold)">Dividend Value (incl. MM)</div><div class="dt-val" style="color:var(--gold)">$'+fmt(r.divBal)+'</div></div>';
  h+='<div class="detail-total" style="margin-top:10px;background:var(--blue-dim);border-color:rgba(59,130,246,.25)"><div><div class="dt-label" style="color:var(--blue)">Grand Total</div><div style="font-size:11px;color:var(--text2);margin-top:1px">Invested: $'+fmt(r.tInv)+'</div></div><div class="dt-val" style="color:var(--blue)">$'+fmt(tv+r.divBal)+'</div></div>';
  $('modalBody').innerHTML=h;
  $('modalOverlay').classList.add('show');
}

async function simulate(){
  if(tot()!==100){$('err').textContent='Allocation must equal 100%';return}
  if(selAmt<=0){$('err').textContent='Enter a monthly investment amount';return}
  const btn=$('runBtn');btn.textContent='⏳ Running...';btn.disabled=true;$('err').textContent='';
  try{
    const now=new Date(),ey=now.getFullYear(),em=now.getMonth()+1,sd=new Date(now);sd.setFullYear(sd.getFullYear()-selYr);
    const sy=sd.getFullYear(),sm=sd.getMonth()+1;
    const active=selected.map(s=>[s,alloc[s]]).filter(([,p])=>p>0);

    /* Fetch ticker data AND money market rates in parallel */
    const [mmData, ...data] = await Promise.all([
      fetch(API+'/mm-rates/monthly?start_year='+sy+'&end_year='+ey).then(r=>r.json()),
      ...active.map(([s])=>fetch(API+'/simulation-data/'+s+'?start_year='+sy+'&start_month='+sm+'&end_year='+ey+'&end_month='+em).then(r=>r.json()))
    ]);

    /* Build MM rate lookup: key "YYYY-MM" → annual rate as decimal (e.g. 5.33 → 0.0533) */
    mmRates={};
    if(Array.isArray(mmData)){mmData.forEach(r=>{mmRates[r.year+'-'+String(r.month).padStart(2,'0')]=r.rate/100})}

    const months=new Set();data.forEach(d=>d.monthly_data?.forEach(m=>months.add(m.year+'-'+String(m.month).padStart(2,'0'))));
    const sorted=[...months].sort();
    const st={};active.forEach(([s,p],i)=>{st[s]={p,sh:0,d:{},totalDivs:0};data[i].monthly_data?.forEach(m=>st[s].d[m.year+'-'+String(m.month).padStart(2,'0')]=m)});

    let tInv=0,tDiv=0,divBal=0;const bk=[];snapshots=[];
    for(const k of sorted){
      const[y,m]=k.split('-').map(Number);let mI=0,mD=0,mS=0;
      const monthSnap={tickers:{},redistributed:false};

      /* Step 0: Apply MM interest on prior dividend balance BEFORE adding new dividends */
      const monthRate=mmRates[k]||0; /* annual rate as decimal */
      divBal=Math.round((divBal*(1+monthRate/12))*100)/100;

      // Step 1: Find which tickers have valid data this month
      const available=[],unavailable=[];
      for(const[s,x]of Object.entries(st)){
        const d=x.d[k];
        if(d&&d.high&&d.high>0) available.push(s);
        else unavailable.push(s);
      }

      // Step 2: Redistribute allocation proportionally if some tickers missing
      let effectiveAlloc={};
      const totalAvailPct=available.reduce((a,s)=>a+st[s].p,0);
      const wasRedist=unavailable.length>0&&available.length>0;
      if(wasRedist) monthSnap.redistributed=true;

      for(const s of available){
        effectiveAlloc[s]=totalAvailPct>0?(st[s].p/totalAvailPct)*100:0;
      }

      // Step 3: Invest using effective allocation
      for(const s of available){
        const x=st[s],d=x.d[k];
        const effPct=effectiveAlloc[s];
        const investAmt=(selAmt*effPct)/100;
        const bought=investAmt/d.high;
        x.sh+=bought;mI+=investAmt;mS+=bought;

        let divsThis=0;
        if(d.dividends){for(const dv of d.dividends){const da=dv.amount*x.sh;tDiv+=da;mD+=da;x.totalDivs+=da;divsThis+=da}}

        const closeP=d.close||0;
        monthSnap.tickers[s]={boughtThisMonth:bought,investedThisMonth:investAmt,buyPrice:d.high,totalShares:x.sh,closePrice:closeP,value:x.sh*closeP,divsThisMonth:divsThis,totalDivs:x.totalDivs,origPct:x.p,effectivePct:effPct};
      }

      // Step 4: Record unavailable tickers
      for(const s of unavailable){
        const x=st[s],d=x.d[k];
        let divsThis=0;
        if(d&&d.dividends){for(const dv of d.dividends){const da=dv.amount*x.sh;tDiv+=da;mD+=da;x.totalDivs+=da;divsThis+=da}}
        const closeP=(d&&d.close)?d.close:0;
        monthSnap.tickers[s]={boughtThisMonth:0,investedThisMonth:0,buyPrice:0,totalShares:x.sh,closePrice:closeP,value:x.sh*closeP,divsThisMonth:divsThis,totalDivs:x.totalDivs,origPct:x.p,effectivePct:0};
      }

      /* Add this month's new dividends to the balance (after interest was applied) */
      divBal=Math.round((divBal+mD)*100)/100;

      tInv+=mI;
      let pv=0;for(const[s,x]of Object.entries(st)){const d=x.d[k];if(d&&d.close)pv+=x.sh*d.close}
      bk.push({year:y,month:m,invested:mI,shares:mS,divs:mD,tInv,tDiv,pv,divBal,mmRate:monthRate});
      snapshots.push(monthSnap);
    }
    breakdownData=bk;
    const last=bk[bk.length-1],ret=last.pv-tInv,retP=(ret/tInv)*100,wDiv=last.pv+tDiv,wDivP=((wDiv-tInv)/tInv)*100;
    showResults({tInv,pv:last.pv,tDiv,ret,retP,wDiv,wDivP,divBal:last.divBal,n:bk.length,bk,active});
  }catch(e){$('err').textContent='Simulation failed: '+e.message}
  finally{btn.textContent='▶ Run Simulation';updBudget()}
}

function showResults(r){
  /* Store results globally for summary card modals */
  window._lastResults=r;
  const el=$('results');
  const divGain=r.divBal-r.tDiv;
  const cards=[
    {l:'Total Invested',v:'$'+fmt(r.tInv),s:r.n+' months × $'+fmt(selAmt),c:'var(--text1)',i:'$',ck:''},
    {l:'Portfolio Value',v:'$'+fmt(r.pv),s:(r.retP>=0?'+':'')+r.retP.toFixed(1)+'% return',c:r.pv>=r.tInv?'var(--accent)':'var(--red)',i:'◆',ck:' clickable-val" onclick="openModal()" title="Click for per-ticker breakdown'},
    {l:'Dividends Earned',v:'$'+fmt(r.tDiv),s:'Cash accumulated',c:'var(--gold)',i:'★',ck:' clickable-val" onclick="showDivSummary()" title="Click for per-ticker dividends'},
    {l:'Div + MM Interest',v:'$'+fmt(r.divBal),s:'MM earned: $'+fmt(divGain),c:'var(--gold)',i:'%',ck:' clickable-val" onclick="showDivValueSummary()" title="Click for details'},
    {l:'Total Value + Dividends',v:'$'+fmt(r.pv+r.divBal),s:((((r.pv+r.divBal)-r.tInv)/r.tInv)*100).toFixed(1)+'% total return',c:'var(--blue)',i:'∑',ck:' clickable-val" onclick="showTotalSummary()" title="Click for breakdown'},
  ];
  let h='<div class="grid-5">';cards.forEach((c,i)=>h+='<div class="card sc fade-up" style="animation-delay:'+i*.1+'s"><div class="icon">'+c.i+'</div><div class="sl">'+c.l+'</div><div class="sv'+c.ck+'" style="color:'+c.c+'">'+c.v+'</div><div class="ss">'+c.s+'</div></div>');h+='</div>';
  h+='<div class="card fade-up" style="animation-delay:.2s;padding:24px;margin-bottom:24px"><h3 class="space" style="font-size:16px;font-weight:600;margin-bottom:16px">Your Allocation</h3><div class="tags">';r.active.forEach(([s,p])=>h+='<div class="tag">'+s+' '+p+'%</div>');h+='</div></div>';
  h+='<div class="card fade-up" style="animation-delay:.3s;padding:24px;margin-bottom:24px"><h3 class="space" style="font-size:18px;font-weight:600;margin-bottom:16px">Growth Over Time</h3><canvas id="chart" style="width:100%;height:300px"></canvas></div>';
  h+='<div class="card fade-up" style="animation-delay:.4s;padding:24px"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"><h3 class="space" style="font-size:18px;font-weight:600">Monthly Breakdown</h3><button class="btn-sm mono" style="background:var(--accent-dim);color:var(--accent)" onclick="togTbl()">Show All ('+r.bk.length+')</button></div>';
  h+='<div style="overflow-x:auto"><table><thead><tr><th style="text-align:left;cursor:pointer" onclick="toggleSortOrder()" id="thMonth">Month ▼</th>'+thWithInfo('Invested','invested')+thWithInfo('Shares','shares')+thWithInfo('Dividends','dividends')+thWithInfo('Div Value','divvalue')+thWithInfo('Portfolio Value','portfolio')+'</tr></thead><tbody id="tblBody"></tbody></table></div></div>';
  el.innerHTML=h;window._bk=r.bk;window._exp=false;window._sortAsc=false;fillTbl(r.bk.slice(-24),r.bk.length-24);setTimeout(()=>drawChart(r.bk),100);el.scrollIntoView({behavior:'smooth',block:'start'});
}
function fillTbl(rows,startIdx){
  if(startIdx<0)startIdx=0;
  /* Build display list with original indices, then apply sort */
  let display=rows.map((r,i)=>({r,gi:startIdx+i}));
  if(!window._sortAsc) display=[...display].reverse();
  $('tblBody').innerHTML=display.map(({r,gi})=>'<tr><td style="color:var(--text2)">'+MO[r.month-1]+' '+r.year+'</td><td class="clickable-cell" onclick="openModal('+gi+',\'invested\')">$'+fmt(r.invested)+'</td><td class="clickable-cell" onclick="openModal('+gi+',\'shares\')" style="color:var(--text2)">'+r.shares.toFixed(4)+'</td><td class="clickable-cell" onclick="openModal('+gi+',\'dividends\')" style="color:'+(r.divs>0?'var(--gold)':'var(--text3)')+'">$'+fmt(r.divs)+'</td><td style="color:var(--gold)">$'+fmt(r.divBal)+'</td><td class="clickable-cell" onclick="openModal('+gi+',\'portfolio\')" style="color:var(--accent);font-weight:600">$'+fmt(r.pv)+'</td></tr>').join('');
}
function togTbl(){window._exp=!window._exp;if(window._exp)fillTbl(window._bk,0);else fillTbl(window._bk.slice(-24),window._bk.length-24)}
function toggleSortOrder(){
  window._sortAsc=!window._sortAsc;
  const th=$('thMonth');if(th)th.textContent='Month '+(window._sortAsc?'▲':'▼');
  if(window._exp)fillTbl(window._bk,0);else fillTbl(window._bk.slice(-24),window._bk.length-24);
}

function drawChart(bk){
  const cv=$('chart');if(!cv)return;const ctx=cv.getContext('2d'),dpr=devicePixelRatio||1,w=cv.offsetWidth,h=cv.offsetHeight;cv.width=w*dpr;cv.height=h*dpr;ctx.scale(dpr,dpr);
  const p={t:30,r:20,b:40,l:75},cw=w-p.l-p.r,ch=h-p.t-p.b,inv=bk.map(r=>r.tInv),vals=bk.map(r=>r.pv),mx=Math.max(...vals,...inv)*1.1;
  ctx.clearRect(0,0,w,h);
  for(let i=0;i<=4;i++){const y=p.t+ch-(ch*i)/4;ctx.strokeStyle='#1e293b';ctx.lineWidth=.5;ctx.beginPath();ctx.moveTo(p.l,y);ctx.lineTo(p.l+cw,y);ctx.stroke();ctx.fillStyle='#64748b';ctx.font='11px JetBrains Mono,monospace';ctx.textAlign='right';ctx.fillText(fmtS((mx*i)/4),p.l-8,y+4)}
  const step=Math.max(1,Math.floor(bk.length/8));ctx.textAlign='center';ctx.font='10px JetBrains Mono,monospace';ctx.fillStyle='#64748b';
  for(let i=0;i<bk.length;i+=step){const x=p.l+(cw*i)/(bk.length-1);ctx.fillText(MO[bk[i].month-1]+' '+String(bk[i].year).slice(2),x,h-10)}
  function line(data,color,fill){ctx.beginPath();data.forEach((v,i)=>{const x=p.l+(cw*i)/(data.length-1),y=p.t+ch-(ch*v)/mx;i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.strokeStyle=color;ctx.lineWidth=2.5;ctx.stroke();if(fill){ctx.lineTo(p.l+cw,p.t+ch);ctx.lineTo(p.l,p.t+ch);ctx.closePath();const g=ctx.createLinearGradient(0,p.t,0,p.t+ch);g.addColorStop(0,fill);g.addColorStop(1,'transparent');ctx.fillStyle=g;ctx.fill()}}
  line(inv,'#64748b88',false);line(vals,'#10b981','rgba(16,185,129,.12)');
  ctx.font='bold 11px JetBrains Mono,monospace';ctx.fillStyle='#10b981';ctx.fillRect(p.l,14,12,3);ctx.textAlign='left';ctx.fillText('Portfolio Value',p.l+18,18);ctx.fillStyle='#64748b';ctx.fillRect(p.l+150,14,12,3);ctx.fillText('Total Invested',p.l+168,18);
}

renderAmts();renderYrs();updBudget();renderAlloc();
fetch(API+'/tickers/active').then(r=>r.json()).then(d=>{
  allTickers=d;const s=$('status');s.style.background='var(--accent-dim)';s.style.color='var(--accent)';
  s.innerHTML='<span style="width:6px;height:6px;border-radius:50%;background:var(--accent);animation:pulse 2s infinite"></span> API Connected &middot; '+d.length+' tickers';
}).catch(()=>{const s=$('status');s.style.background='var(--red-dim)';s.style.color='var(--red)';s.innerHTML='<span style="width:6px;height:6px;border-radius:50%;background:var(--red)"></span> API Offline';$('err').textContent='Cannot reach API at localhost:8000. Make sure uvicorn is running.'});
