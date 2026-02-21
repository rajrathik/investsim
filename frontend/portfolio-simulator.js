const API="/api";
const AMTS=[500,1000,2000,5000];
const MO=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
let allTickers=[],selected=[],alloc={},selAmt=1000,selGrowth=0,selYr=10;
let snapshots=null,breakdownData=null;

/* authFetch is plain fetch (no auth required for public pages) */
async function authFetch(url,options={}){
  return fetch(url,options);
}

/* Load tickers on page load */
document.addEventListener('DOMContentLoaded',function(){
  loadTickers();
});

async function loadTickers(){
  try{
    const d=await authFetch(API+'/tickers/active').then(r=>r.json());
    allTickers=d;
  }catch(e){$('err').textContent='Cannot reach API. Make sure uvicorn is running and you are logged in.';}
}

/* Column info tooltips — shown on hover of the * icon in table headers */
const COL_INFO={
  deposit:'New money deposited this month (base amount + annual growth). This is the fresh deposit before any carryover from prior months.',
  invested:'Actual $ spent this month (integer shares × high price). Unspent remainder stays in each ticker\'s bucket until enough to buy a share.',
  totalinvested:'Running total of all monthly investments to date.',
  shares:'Whole shares purchased this month = floor(accumulated $ ÷ monthly high price). Each ticker accumulates until it can afford a share.',
  totalshares:'Running total of all shares held across all tickers.',
  dividends:'Cash dividends received based on shares held × dividend per share. Not reinvested.',
  divvalue:'Accumulated dividends and money market interest on accrued cash.',
  portfolio:'Equity value: shares held × close price for each ticker.',
  mmonly:'What if you invested the same monthly amount entirely in money market at the federal funds rate instead of securities.'
};
let mmRates={}; /* key: "YYYY-MM" → annual rate as decimal e.g. 0.05 */

function $(id){return document.getElementById(id)}
function fmt(n){return(n||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}
function fmtW(n){return(n||0).toLocaleString('en-US',{minimumFractionDigits:0,maximumFractionDigits:0})}
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
$('growthInp').addEventListener('input',function(){selGrowth=Math.max(0,parseInt(this.value)||0)});
function renderYrs(){
  let h='<select id="yrSel" class="yr-select" onchange="setYr(+this.value)">';
  for(let y=1;y<=20;y++)h+='<option value="'+y+'"'+(selYr===y?' selected':'')+'>'+y+' Year'+(y>1?'s':'')+'</option>';
  h+='</select>';
  $('yrBtns').innerHTML=h;
}
function setYr(y){selYr=Math.max(1,Math.min(20,y));$('yrInp').value=selYr;renderYrs()}
$('yrInp').addEventListener('input',function(){selYr=Math.max(1,Math.min(20,parseInt(this.value)||1));renderYrs()});

const si=$('searchInp'),dd=$('dropdown');
function showDD(q){
  q=(q||'').toLowerCase().trim();
  let list=q?allTickers.filter(t=>t.symbol.toLowerCase().includes(q)||(t.name||'').toLowerCase().includes(q)):allTickers;
  if(!list.length){dd.innerHTML='<div style="padding:14px;color:var(--text3);text-align:center">No matches</div>';dd.classList.add('show');return}
  dd.innerHTML=list.map(t=>{const sel=selected.includes(t.symbol);return'<div class="dd-item" onclick="event.stopPropagation();togTk(\''+t.symbol+'\')"><span class="dd-cb-wrap"><input type="checkbox" class="dd-cb" '+(sel?'checked':'')+' tabindex="-1"><span class="dd-sym">'+t.symbol+'</span><span class="dd-name">'+(t.name||'')+'</span></span></div>'}).join('');
  dd.classList.add('show');
}
si.addEventListener('input',function(){showDD(this.value)});
si.addEventListener('focus',function(){showDD(this.value)});
si.addEventListener('click',function(){showDD(this.value)});
document.addEventListener('click',function(e){if(!e.target.closest('.search-wrap'))dd.classList.remove('show')});
function togTk(s){
  if(selected.includes(s)){selected=selected.filter(x=>x!==s);delete alloc[s]}
  else{selected.push(s);alloc[s]=0}
  renderChips();renderAlloc();updBudget();
  /* Re-render dropdown in place so it stays open for multi-select */
  showDD(si.value);
  /* Keep focus on search so user can continue typing/browsing */
  setTimeout(function(){si.focus()},10);
}
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
  $('allocList').innerHTML=selected.map(s=>{const t=getTk(s),p=alloc[s]||0;return'<div class="ar"><div style="min-width:90px"><div class="sym">'+s+'</div><div class="nm">'+(t?.name||'')+'</div></div><div class="stepper"><button class="step-btn step-minus'+(p<=0?' disabled':'')+'" onclick="stepA(\''+s+'\',-5)"'+(p<=0?' disabled':'')+'>−</button><span class="step-val">'+p+'%</span><button class="step-btn step-plus'+(p>=100?' disabled':'')+'" onclick="stepA(\''+s+'\',5)"'+(p>=100?' disabled':'')+'>+</button></div></div>'}).join('');
}
function stepA(s,delta){const cur=alloc[s]||0;const nv=Math.max(0,Math.min(100,cur+delta));alloc[s]=nv;renderAlloc();updBudget()}
function setA(s,v){alloc[s]=v;renderAlloc();updBudget()}
function resetA(){selected=[];alloc={};si.value='';dd.classList.remove('show');snapshots=null;breakdownData=null;renderChips();renderAlloc();updBudget();$('results').innerHTML=''}
function eqSplit(){if(!selected.length)return;const n=selected.length,base=Math.floor(100/n/5)*5,rem=100-base*n;let carry=rem;selected.forEach((s,i)=>{let extra=0;if(carry>=5){extra=5;carry-=5}alloc[s]=base+extra});renderAlloc();updBudget()}

function openModal(idx,context){$('modalOverlay').classList.add('show');if(idx===undefined)renderPortfolioModal();else if(context)renderContextModal(idx,context);else renderMonthModal(idx)}
function closeModal(){$('modalOverlay').classList.remove('show')}

function renderPortfolioModal(){
  if(!snapshots||!snapshots.length){$('modalBody').innerHTML='<p style="color:var(--text3)">No data</p>';return}
  const snap=snapshots[snapshots.length-1];
  $('modalTitle').textContent='Portfolio Breakdown';
  $('modalSub').textContent='Final snapshot as of last available month';
  let h='',tv=0;const syms=Object.keys(snap.tickers);
  syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);tv+=d.value;
    h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val">$'+fmt(d.value)+'</div><div class="d-sub">'+d.totalShares.toLocaleString()+' shares × $'+fmt(d.closePrice)+' close</div><div class="d-sub2">'+d.origPct+'% target alloc · Divs earned: $'+fmt(d.totalDivs)+'</div></div></div>'});
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
      const accumNote=d.accumBal>0?'<div class="d-sub2" style="color:var(--text3)">$'+fmt(d.accumBal)+' remaining in bucket</div>':'';
      h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val">+'+d.boughtThisMonth.toLocaleString()+' shares</div><div class="d-sub">$'+fmt(d.investedThisMonth)+' invested at $'+fmt(d.buyPrice)+' high</div>'+note+accumNote+'</div></div>'
    } else if(d.origPct>0&&d.effectivePct>0){
      h+='<div class="detail-row" style="opacity:.7"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--text3)">Accumulating</div><div class="d-sub">$'+fmt(d.accumBal)+' saved — waiting for enough to buy a share</div></div></div>'
    } else if(d.origPct>0){
      h+='<div class="detail-row" style="opacity:.5"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--text3)">No data</div><div class="d-sub">Allocation redistributed to other tickers</div></div></div>'
    }
  });
  const anyDiv=syms.some(s=>snap.tickers[s].divsThisMonth>0);
  if(anyDiv){
    h+='<div class="section-label">Dividends This Month</div>';
    syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);
      if(d.divsThisMonth>0)h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--gold)">$'+fmt(d.divsThisMonth)+'</div><div class="d-sub">on '+d.totalShares.toLocaleString()+' shares held</div></div></div>'});
  }
  h+='<div class="section-label">Running Portfolio Totals</div>';
  let tv=0;
  syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);tv+=d.value;
    h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val">$'+fmt(d.value)+'</div><div class="d-sub">'+d.totalShares.toLocaleString()+' total shares × $'+fmt(d.closePrice)+' close</div><div class="d-sub2">Total divs to date: $'+fmt(d.totalDivs)+'</div></div></div>'});
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
    $('modalSub').textContent='How $'+fmt(bk.invested)+' was spent across tickers';
    let totalInv=0;
    syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);
      if(d.investedThisMonth>0){totalInv+=d.investedThisMonth;
        let note='';if(d.effectivePct!==d.origPct)note='<div class="redist-note" style="font-size:10px;padding:3px 8px;margin-top:1px">'+d.origPct+'% → '+d.effectivePct.toFixed(1)+'%</div>';
        const accumNote=d.accumBal>0?'<div class="d-sub2" style="color:var(--text3)">$'+fmt(d.accumBal)+' remaining in bucket</div>':'';
        h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val">$'+fmt(d.investedThisMonth)+'</div><div class="d-sub">at $'+fmt(d.buyPrice)+' high</div>'+note+accumNote+'</div></div>'}
      else if(d.origPct>0&&d.effectivePct>0){
        h+='<div class="detail-row" style="opacity:.7"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--text3);font-size:13px">Accumulating</div><div class="d-sub">$'+fmt(d.accumBal)+' in bucket</div></div></div>'}
      else if(d.origPct>0){h+='<div class="detail-row" style="opacity:.4"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--text3);font-size:13px">No data</div></div></div>'}
    });
    h+='<div class="detail-total"><div class="dt-label">Total Invested</div><div class="dt-val">$'+fmt(totalInv)+'</div></div>';
  }

  else if(context==='shares'){
    $('modalTitle').textContent=monthLabel+' — Shares Purchased';
    $('modalSub').textContent='New shares acquired this month (per-ticker accumulation)';
    let totalShares=0;
    syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);
      if(d.boughtThisMonth>0){totalShares+=d.boughtThisMonth;
        const accumNote=d.accumBal>0?'<div class="d-sub2" style="color:var(--text3)">$'+fmt(d.accumBal)+' remaining in bucket</div>':'';
        h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val">+'+d.boughtThisMonth.toLocaleString()+'</div><div class="d-sub">$'+fmt(d.investedThisMonth)+' ÷ $'+fmt(d.buyPrice)+'</div>'+accumNote+'</div></div>'}
      else if(d.origPct>0&&d.effectivePct>0){
        h+='<div class="detail-row" style="opacity:.7"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--text3);font-size:13px">Accumulating</div><div class="d-sub">$'+fmt(d.accumBal)+' in bucket</div></div></div>'}
      else if(d.origPct>0){h+='<div class="detail-row" style="opacity:.4"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--text3);font-size:13px">No data</div></div></div>'}
    });
    h+='<div class="detail-total"><div class="dt-label">Total Shares Bought</div><div class="dt-val">'+totalShares.toLocaleString()+'</div></div>';
  }

  else if(context==='totalshares'){
    $('modalTitle').textContent=monthLabel+' — Total Shares Held';
    $('modalSub').textContent='Accumulated shares across all tickers';
    let grandTotal=0;
    syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);grandTotal+=d.totalShares;
      h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val">'+d.totalShares.toLocaleString()+' shares</div><div class="d-sub">Value: $'+fmt(d.value)+'</div></div></div>'});
    h+='<div class="detail-total"><div class="dt-label">Total Shares</div><div class="dt-val">'+grandTotal.toLocaleString()+'</div></div>';
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
          h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--gold)">$'+fmt(d.divsThisMonth)+'</div><div class="d-sub">on '+d.totalShares.toLocaleString()+' shares</div></div></div>'}
      });
      h+='<div class="detail-total" style="background:var(--gold-dim);border-color:rgba(245,158,11,.25)"><div class="dt-label" style="color:var(--gold)">Total Dividends</div><div class="dt-val" style="color:var(--gold)">$'+fmt(totalDiv)+'</div></div>';
    }
  }

  else if(context==='portfolio'){
    $('modalTitle').textContent=monthLabel+' — Equity Value';
    $('modalSub').textContent='Value split across holdings';
    let tv=0;
    syms.forEach(s=>{const d=snap.tickers[s],t=getTk(s);tv+=d.value;
      h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--accent)">$'+fmt(d.value)+'</div><div class="d-sub">'+d.totalShares.toLocaleString()+' × $'+fmt(d.closePrice)+'</div></div></div>'});
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
    h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--gold)">$'+fmt(d.totalDivs)+'</div><div class="d-sub">'+d.totalShares.toLocaleString()+' shares held</div></div></div>'});
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
    h+='<div class="detail-row"><div><div class="d-sym">'+s+'</div><div class="d-name">'+(t?.name||'')+'</div></div><div class="d-nums"><div class="d-val" style="color:var(--accent)">$'+fmt(d.value)+'</div><div class="d-sub">'+d.totalShares.toLocaleString()+' × $'+fmt(d.closePrice)+'</div></div></div>'});
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

/* Summary card: MM Only Benchmark — what if all investment went to money market */
function showMMOnlySummary(){
  if(!window._lastResults)return;
  const r=window._lastResults;
  const mmGain=r.mmOnlyBal-r.tInv;
  const etfTotal=r.pv+r.divBal;
  const etfGain=etfTotal-r.tInv;
  $('modalTitle').textContent='Money Market Only Benchmark';
  $('modalSub').textContent='What if you invested $'+fmt(selAmt)+'/month'+(selGrowth>0?' (growing $'+fmt(selGrowth)+'/yr)':'')+' entirely in money market?';
  let h='';
  h+='<div class="section-label">Money Market Only</div>';
  h+='<div class="detail-row"><div><div class="d-sym" style="color:var(--text2)">Total Invested</div><div class="d-name">'+r.n+' months'+(selGrowth>0?' (base $'+fmt(selAmt)+' + $'+fmt(selGrowth)+'/yr growth)':' × $'+fmt(selAmt))+'</div></div><div class="d-nums"><div class="d-val">$'+fmt(r.tInv)+'</div></div></div>';
  h+='<div class="detail-row"><div><div class="d-sym" style="color:var(--accent)">Interest Earned</div><div class="d-name">At federal funds rate (monthly compounding)</div></div><div class="d-nums"><div class="d-val" style="color:var(--accent)">$'+fmt(mmGain)+'</div></div></div>';
  h+='<div class="detail-total" style="background:var(--border);border-color:var(--text3)"><div><div class="dt-label" style="color:var(--text2)">MM Only Value</div><div style="font-size:11px;color:var(--text3);margin-top:1px">+'+(mmGain/r.tInv*100).toFixed(1)+'% return</div></div><div class="dt-val" style="color:var(--text2)">$'+fmt(r.mmOnlyBal)+'</div></div>';
  h+='<div class="section-label" style="margin-top:16px">Your Portfolio (for comparison)</div>';
  h+='<div class="detail-row"><div><div class="d-sym" style="color:var(--accent)">Portfolio + Dividends</div><div class="d-name">Holdings value + dividend balance with MM interest</div></div><div class="d-nums"><div class="d-val" style="color:var(--accent)">$'+fmt(etfTotal)+'</div></div></div>';
  const diff=etfTotal-r.mmOnlyBal;
  const diffColor=diff>=0?'var(--accent)':'var(--red)';
  h+='<div class="detail-total" style="margin-top:8px;background:'+(diff>=0?'var(--accent-dim)':'var(--red-dim)')+';border-color:'+(diff>=0?'rgba(16,185,129,.25)':'rgba(239,68,68,.25)')+'"><div><div class="dt-label" style="color:'+diffColor+'">Portfolio vs MM Only</div><div style="font-size:11px;color:var(--text2);margin-top:1px">Your investment strategy '+(diff>=0?'outperformed':'underperformed')+' by</div></div><div class="dt-val" style="color:'+diffColor+'">'+(diff>=0?'+':'')+' $'+fmt(diff)+'</div></div>';
  $('modalBody').innerHTML=h;
  $('modalOverlay').classList.add('show');
}

async function simulate(){
  if(tot()!==100){$('err').textContent='Allocation must equal 100%';return}
  if(selAmt<=0){$('err').textContent='Enter a monthly investment amount';return}
  const btn=$('runBtn');btn.textContent='⏳ Running...';btn.disabled=true;$('err').textContent='';
  try{
    /* Stop at prior year-end (December of last complete year) */
    const now=new Date(),ey=now.getFullYear()-1,em=12;
    const sd=new Date(ey-selYr+1,0,1);
    const sy=sd.getFullYear(),sm=1;
    const active=selected.map(s=>[s,alloc[s]]).filter(([,p])=>p>0);

    /* Fetch ticker data AND money market rates in parallel */
    const [mmData, ...data] = await Promise.all([
      authFetch(API+'/mm-rates/monthly?start_year='+sy+'&end_year='+ey).then(r=>r.json()),
      ...active.map(([s])=>authFetch(API+'/simulation-data/'+s+'?start_year='+sy+'&start_month='+sm+'&end_year='+ey+'&end_month='+em).then(r=>r.json()))
    ]);

    /* Build MM rate lookup: key "YYYY-MM" → annual rate as decimal (e.g. 5.33 → 0.0533) */
    mmRates={};
    if(Array.isArray(mmData)){mmData.forEach(r=>{mmRates[r.year+'-'+String(r.month).padStart(2,'0')]=r.rate/100})}

    const months=new Set();data.forEach(d=>d.monthly_data?.forEach(m=>months.add(m.year+'-'+String(m.month).padStart(2,'0'))));
    const sorted=[...months].sort();
    const st={};active.forEach(([s,p],i)=>{st[s]={p,sh:0,d:{},totalDivs:0};data[i].monthly_data?.forEach(m=>st[s].d[m.year+'-'+String(m.month).padStart(2,'0')]=m)});

    /* Per-ticker accumulation buckets: each ticker keeps its own unspent $ */
    const accum={};active.forEach(([s])=>accum[s]=0);
    let tInv=0,tDiv=0,divBal=0,mmOnlyBal=0;const bk=[];snapshots=[];
    for(const k of sorted){
      const[y,m]=k.split('-').map(Number);let mI=0,mD=0,mS=0;
      const monthSnap={tickers:{},redistributed:false};

      /* Step 0: Apply MM interest on prior dividend balance BEFORE adding new dividends */
      const monthRate=mmRates[k]||0; /* annual rate as decimal */
      const mmIntThisMonth=Math.round((divBal*monthRate/12)*100)/100;
      divBal=Math.round((divBal+mmIntThisMonth)*100)/100;

      /* This month's investable amount = base + annual growth */
      const yearOffset=y-sy;
      const monthBudget=selAmt+(yearOffset*selGrowth);

      /* MM-only benchmark: grow prior balance at MM rate, then add this month's investment */
      mmOnlyBal=Math.round((mmOnlyBal*(1+monthRate/12))*100)/100;
      mmOnlyBal=Math.round((mmOnlyBal+monthBudget)*100)/100;

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

      // Step 3: Invest using per-ticker accumulate-then-buy
      for(const s of available){
        const x=st[s],d=x.d[k];
        const effPct=effectiveAlloc[s];
        const allocAmt=(monthBudget*effPct)/100;
        accum[s]=Math.round((accum[s]+allocAmt)*100)/100; /* add this month's allocation to bucket */
        const bought=Math.floor(accum[s]/d.high);          /* integer shares from accumulated $ */
        const spent=bought*d.high;                          /* actual $ spent */
        accum[s]=Math.round((accum[s]-spent)*100)/100;      /* remainder stays in this ticker's bucket */
        x.sh+=bought;mI+=spent;mS+=bought;

        let divsThis=0;
        if(d.dividends){for(const dv of d.dividends){const da=dv.amount*x.sh;tDiv+=da;mD+=da;x.totalDivs+=da;divsThis+=da}}

        const closeP=d.close||0;
        monthSnap.tickers[s]={boughtThisMonth:bought,investedThisMonth:spent,buyPrice:d.high,totalShares:x.sh,closePrice:closeP,value:x.sh*closeP,divsThisMonth:divsThis,totalDivs:x.totalDivs,origPct:x.p,effectivePct:effPct,accumBal:accum[s]};
      }

      // Step 4: Record unavailable tickers
      for(const s of unavailable){
        const x=st[s],d=x.d[k];
        let divsThis=0;
        if(d&&d.dividends){for(const dv of d.dividends){const da=dv.amount*x.sh;tDiv+=da;mD+=da;x.totalDivs+=da;divsThis+=da}}
        const closeP=(d&&d.close)?d.close:0;
        monthSnap.tickers[s]={boughtThisMonth:0,investedThisMonth:0,buyPrice:0,totalShares:x.sh,closePrice:closeP,value:x.sh*closeP,divsThisMonth:divsThis,totalDivs:x.totalDivs,origPct:x.p,effectivePct:0,accumBal:accum[s]||0};
      }

      /* Add this month's new dividends to the balance (after interest was applied) */
      divBal=Math.round((divBal+mD)*100)/100;

      tInv+=mI;
      let pv=0,totalSh=0;for(const[s,x]of Object.entries(st)){const d=x.d[k];if(d&&d.close)pv+=x.sh*d.close;totalSh+=x.sh}
      bk.push({year:y,month:m,deposit:monthBudget,invested:mI,shares:mS,totalShares:totalSh,divs:mD,tInv,tDiv,pv,divBal,mmRate:monthRate,mmOnlyBal,mmInt:mmIntThisMonth});
      snapshots.push(monthSnap);
    }
    breakdownData=bk;
    const last=bk[bk.length-1],ret=last.pv-tInv,retP=(ret/tInv)*100,wDiv=last.pv+tDiv,wDivP=((wDiv-tInv)/tInv)*100;
    showResults({tInv,pv:last.pv,tDiv,ret,retP,wDiv,wDivP,divBal:last.divBal,mmOnlyBal:last.mmOnlyBal,n:bk.length,bk,active});
  }catch(e){$('err').textContent='Simulation failed: '+e.message}
  finally{btn.textContent='▶ Run Simulation';updBudget()}
}

function showResults(r){
  /* Store results globally for summary card modals */
  window._lastResults=r;
  const el=$('results');
  const divGain=r.divBal-r.tDiv;
  const mmOnlyRetP=((r.mmOnlyBal-r.tInv)/r.tInv*100).toFixed(1);
  const cards=[
    {l:'Total Invested',v:'$'+fmtW(r.tInv),s:r.n+' months'+(selGrowth>0?' (base $'+fmtW(selAmt)+' + $'+fmtW(selGrowth)+'/yr)':' × $'+fmtW(selAmt)),c:'var(--text1)',i:'$',ck:''},
    {l:'Equity Value',v:'$'+fmtW(r.pv),s:(r.retP>=0?'+':'')+r.retP.toFixed(1)+'% return',c:r.pv>=r.tInv?'var(--accent)':'var(--red)',i:'◆',ck:' clickable-val" onclick="openModal()" title="Click for per-ticker breakdown'},
    {l:'Dividends Earned',v:'$'+fmtW(r.tDiv),s:'Cash accumulated',c:'var(--gold)',i:'★',ck:' clickable-val" onclick="showDivSummary()" title="Click for per-ticker dividends'},
    {l:'Cash Accrual',v:'$'+fmtW(r.divBal),s:'MM earned: $'+fmtW(divGain),c:'var(--gold)',i:'%',ck:' clickable-val" onclick="showDivValueSummary()" title="Click for details'},
    {l:'Portfolio Balance',v:'$'+fmtW(r.pv+r.divBal),s:((((r.pv+r.divBal)-r.tInv)/r.tInv)*100).toFixed(1)+'% total return',c:'var(--blue)',i:'∑',ck:' clickable-val" onclick="showTotalSummary()" title="Click for breakdown'},
    {l:'MMF Value',v:'$'+fmtW(r.mmOnlyBal),s:'+'+mmOnlyRetP+'% return',c:'var(--text2)',i:'⊞',ck:' clickable-val" onclick="showMMOnlySummary()" title="Click for details'},
  ];
  let h='<div class="grid-6">';cards.forEach((c,i)=>h+='<div class="card sc fade-up" style="animation-delay:'+i*.1+'s"><div class="icon">'+c.i+'</div><div class="sl">'+c.l+'</div><div class="sv'+c.ck+'" style="color:'+c.c+'">'+c.v+'</div><div class="ss">'+c.s+'</div></div>');h+='</div>';
  h+='<div class="card fade-up" style="animation-delay:.2s;padding:24px;margin-bottom:24px"><h3 class="space" style="font-size:16px;font-weight:600;margin-bottom:16px">Your Allocation</h3><div class="tags">';r.active.forEach(([s,p])=>h+='<div class="tag">'+s+' '+p+'%</div>');h+='</div></div>';
  /* Chart 1: Growth Over Time — interactive with click tooltip */
  h+='<div class="card fade-up" style="animation-delay:.3s;padding:24px;margin-bottom:24px"><h3 class="space" style="font-size:18px;font-weight:600;margin-bottom:16px">Growth Over Time</h3><div class="chart-wrap" id="chartWrap1"><canvas id="chart" style="width:100%;height:300px;cursor:crosshair"></canvas><div class="chart-crosshair" id="chartCross1"></div><div class="chart-tooltip" id="chartTip1"></div></div></div>';
  /* Chart 2: Dividend Balance + MM Interest growth */
  h+='<div class="card fade-up" style="animation-delay:.35s;padding:24px;margin-bottom:24px"><h3 class="space" style="font-size:18px;font-weight:600;margin-bottom:16px">Dividend Earned</h3><div class="chart-wrap" id="chartWrap2"><canvas id="chart2" style="width:100%;height:250px;cursor:crosshair"></canvas><div class="chart-crosshair" id="chartCross2"></div><div class="chart-tooltip" id="chartTip2"></div></div></div>';
  h+='<div class="card fade-up" style="animation-delay:.4s;padding:24px"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"><h3 class="space" style="font-size:18px;font-weight:600">Monthly Breakdown</h3><button class="btn-sm mono" style="background:var(--accent-dim);color:var(--accent)" onclick="togTbl()">Show All ('+r.bk.length+')</button></div>';
  h+='<div style="overflow-x:auto"><table><thead><tr><th style="text-align:left;cursor:pointer" onclick="toggleSortOrder()" id="thMonth">Month ▼</th>'+thWithInfo('Deposit','deposit')+thWithInfo('Invested','invested')+thWithInfo('Total Invested','totalinvested')+thWithInfo('Shares','shares')+thWithInfo('Total Shares','totalshares')+thWithInfo('Dividends','dividends')+thWithInfo('Cash Accrual','divvalue')+thWithInfo('Equity Value','portfolio')+thWithInfo('MMF Value','mmonly')+'</tr></thead><tbody id="tblBody"></tbody></table></div></div>';
  /* Tax Impact section */
  h+='<div class="card fade-up" style="animation-delay:.5s;padding:24px;margin-top:24px"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px"><h3 class="space" style="font-size:18px;font-weight:600">Tax Impact</h3><div style="display:flex;align-items:center;gap:8px"><label style="font-size:12px;color:var(--text3);font-family:JetBrains Mono,monospace">Tax Rate %</label><input type="number" id="taxRate" class="inp" style="width:80px;margin:0;padding:6px 10px;font-size:14px" value="30" min="0" max="60" step="1" oninput="renderTaxImpact()"></div></div><div id="taxBody"></div></div>';
  el.innerHTML=h;window._bk=r.bk;window._exp=false;window._sortAsc=false;fillTbl(r.bk.slice(-24),r.bk.length-24);
  setTimeout(()=>{drawChart(r.bk);drawDivChart(r.bk);setupChartInteraction(r.bk);renderTaxImpact()},100);
  el.scrollIntoView({behavior:'smooth',block:'start'});
}
/* Re-render charts when theme toggles so Canvas picks up new colors */
window.addEventListener('themechange',function(){if(window._bk){drawChart(window._bk);drawDivChart(window._bk)}});
function fillTbl(rows,startIdx){
  if(startIdx<0)startIdx=0;
  /* Build display list with original indices, then apply sort */
  let display=rows.map((r,i)=>({r,gi:startIdx+i}));
  if(!window._sortAsc) display=[...display].reverse();
  $('tblBody').innerHTML=display.map(({r,gi})=>'<tr><td style="color:var(--text2)">'+MO[r.month-1]+' '+r.year+'</td><td style="color:var(--text2)">$'+fmt(r.deposit)+'</td><td class="clickable-cell" onclick="openModal('+gi+',\'invested\')">$'+fmt(r.invested)+'</td><td>$'+fmt(r.tInv)+'</td><td class="clickable-cell" onclick="openModal('+gi+',\'shares\')" style="color:var(--text2)">'+r.shares.toLocaleString()+'</td><td class="clickable-cell" onclick="openModal('+gi+',\'totalshares\')" style="color:var(--text2)">'+r.totalShares.toLocaleString()+'</td><td class="clickable-cell" onclick="openModal('+gi+',\'dividends\')" style="color:'+(r.divs>0?'var(--gold)':'var(--text3)')+'">$'+fmt(r.divs)+'</td><td style="color:var(--gold)">$'+fmt(r.divBal)+'</td><td class="clickable-cell" onclick="openModal('+gi+',\'portfolio\')" style="color:var(--accent);font-weight:600">$'+fmt(r.pv)+'</td><td style="color:var(--text2)">$'+fmt(r.mmOnlyBal)+'</td></tr>').join('');
}
function togTbl(){window._exp=!window._exp;if(window._exp)fillTbl(window._bk,0);else fillTbl(window._bk.slice(-24),window._bk.length-24)}
function toggleSortOrder(){
  window._sortAsc=!window._sortAsc;
  const th=$('thMonth');if(th)th.textContent='Month '+(window._sortAsc?'▲':'▼');
  if(window._exp)fillTbl(window._bk,0);else fillTbl(window._bk.slice(-24),window._bk.length-24);
}

function drawChart(bk){
  const cv=$('chart');if(!cv)return;const ctx=cv.getContext('2d'),dpr=devicePixelRatio||1,w=cv.offsetWidth,h=cv.offsetHeight;cv.width=w*dpr;cv.height=h*dpr;ctx.scale(dpr,dpr);
  const p={t:30,r:20,b:40,l:75},cw=w-p.l-p.r,ch=h-p.t-p.b;
  const inv=bk.map(r=>r.tInv),vals=bk.map(r=>r.pv),mmOnly=bk.map(r=>r.mmOnlyBal);
  const mx=Math.max(...vals,...inv,...mmOnly)*1.1;
  /* Store geometry for interactive tooltip */
  window._chart1={p,cw,ch,mx,bk,w,h};
  ctx.clearRect(0,0,w,h);
  for(let i=0;i<=4;i++){const y=p.t+ch-(ch*i)/4;ctx.strokeStyle=THEME.grid;ctx.lineWidth=.5;ctx.beginPath();ctx.moveTo(p.l,y);ctx.lineTo(p.l+cw,y);ctx.stroke();ctx.fillStyle=THEME.axis;ctx.font='11px JetBrains Mono,monospace';ctx.textAlign='right';ctx.fillText(fmtS((mx*i)/4),p.l-8,y+4)}
  const step=Math.max(1,Math.floor(bk.length/8));ctx.textAlign='center';ctx.font='10px JetBrains Mono,monospace';ctx.fillStyle=THEME.axis;
  for(let i=0;i<bk.length;i+=step){const x=p.l+(cw*i)/(bk.length-1);ctx.fillText(MO[bk[i].month-1]+' '+String(bk[i].year).slice(2),x,h-10)}
  function line(data,color,fill,dash){ctx.beginPath();if(dash)ctx.setLineDash(dash);else ctx.setLineDash([]);data.forEach((v,i)=>{const x=p.l+(cw*i)/(data.length-1),y=p.t+ch-(ch*v)/mx;i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.strokeStyle=color;ctx.lineWidth=2.5;ctx.stroke();ctx.setLineDash([]);if(fill){ctx.lineTo(p.l+cw,p.t+ch);ctx.lineTo(p.l,p.t+ch);ctx.closePath();const g=ctx.createLinearGradient(0,p.t,0,p.t+ch);g.addColorStop(0,fill);g.addColorStop(1,'transparent');ctx.fillStyle=g;ctx.fill()}}
  line(inv,THEME.axis+'88',false);line(mmOnly,THEME.text2,false,[6,4]);line(vals,'#10b981','rgba(16,185,129,.12)');
  /* Legend */
  ctx.font='bold 11px JetBrains Mono,monospace';ctx.textAlign='left';
  ctx.fillStyle='#10b981';ctx.fillRect(p.l,14,12,3);ctx.fillText('Portfolio Value',p.l+18,18);
  ctx.fillStyle=THEME.axis;ctx.fillRect(p.l+150,14,12,3);ctx.fillText('Total Invested',p.l+168,18);
  ctx.fillStyle=THEME.text2;ctx.setLineDash([4,3]);ctx.beginPath();ctx.moveTo(p.l+300,15.5);ctx.lineTo(p.l+312,15.5);ctx.stroke();ctx.setLineDash([]);ctx.fillText('Money Market Return',p.l+318,18);
}

function drawDivChart(bk){
  const cv=$('chart2');if(!cv)return;const ctx=cv.getContext('2d'),dpr=devicePixelRatio||1,w=cv.offsetWidth,h=cv.offsetHeight;cv.width=w*dpr;cv.height=h*dpr;ctx.scale(dpr,dpr);
  const p={t:30,r:20,b:40,l:75},cw=w-p.l-p.r,ch=h-p.t-p.b;
  const divBals=bk.map(r=>r.divBal),rawDivs=bk.map(r=>r.tDiv);
  const mx=Math.max(...divBals,1)*1.1;
  /* Store geometry for interactive tooltip */
  window._chart2={p,cw,ch,mx,bk,w,h};
  ctx.clearRect(0,0,w,h);
  for(let i=0;i<=4;i++){const y=p.t+ch-(ch*i)/4;ctx.strokeStyle=THEME.grid;ctx.lineWidth=.5;ctx.beginPath();ctx.moveTo(p.l,y);ctx.lineTo(p.l+cw,y);ctx.stroke();ctx.fillStyle=THEME.axis;ctx.font='11px JetBrains Mono,monospace';ctx.textAlign='right';ctx.fillText(fmtS((mx*i)/4),p.l-8,y+4)}
  const step=Math.max(1,Math.floor(bk.length/8));ctx.textAlign='center';ctx.font='10px JetBrains Mono,monospace';ctx.fillStyle=THEME.axis;
  for(let i=0;i<bk.length;i+=step){const x=p.l+(cw*i)/(bk.length-1);ctx.fillText(MO[bk[i].month-1]+' '+String(bk[i].year).slice(2),x,h-10)}
  function line(data,color,fill){ctx.beginPath();data.forEach((v,i)=>{const x=p.l+(cw*i)/(data.length-1),y=p.t+ch-(ch*v)/mx;i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.strokeStyle=color;ctx.lineWidth=2.5;ctx.stroke();if(fill){ctx.lineTo(p.l+cw,p.t+ch);ctx.lineTo(p.l,p.t+ch);ctx.closePath();const g=ctx.createLinearGradient(0,p.t,0,p.t+ch);g.addColorStop(0,fill);g.addColorStop(1,'transparent');ctx.fillStyle=g;ctx.fill()}}
  line(rawDivs,THEME.axis+'88',false);line(divBals,'#f59e0b','rgba(245,158,11,.12)');
  ctx.font='bold 11px JetBrains Mono,monospace';ctx.textAlign='left';
  ctx.fillStyle='#f59e0b';ctx.fillRect(p.l,14,12,3);ctx.fillText('Dividend Invested in Money Market',p.l+18,18);
  ctx.fillStyle=THEME.axis;ctx.fillRect(p.l+300,14,12,3);ctx.fillText('Dividend Accumulated',p.l+318,18);
}

function setupChartInteraction(bk){
  /* Attach mouse/touch handlers to both charts for interactive tooltips */
  function attachChart(canvasId,crossId,tipId,chartKey,tipBuilder){
    const cv=$(canvasId);if(!cv)return;
    const wrap=cv.parentElement;
    function handler(e){
      const geo=window[chartKey];if(!geo)return;
      const rect=cv.getBoundingClientRect();
      const mx=e.clientX-rect.left;
      /* Find nearest data index */
      const idx=Math.round(((mx-geo.p.l)/geo.cw)*(bk.length-1));
      if(idx<0||idx>=bk.length){$(tipId).classList.remove('show');$(crossId).style.display='none';return}
      const x=geo.p.l+(geo.cw*idx)/(bk.length-1);
      const cross=$(crossId);cross.style.display='block';cross.style.left=x+'px';cross.style.top=geo.p.t+'px';cross.style.height=geo.ch+'px';
      const tip=$(tipId);
      tip.innerHTML=tipBuilder(bk[idx],idx);
      tip.classList.add('show');
      /* Position tooltip — flip if near right edge */
      const tipW=tip.offsetWidth||200;
      if(x+tipW+16>wrap.offsetWidth)tip.style.left=(x-tipW-12)+'px';
      else tip.style.left=(x+12)+'px';
      tip.style.top=geo.p.t+'px';
    }
    cv.addEventListener('mousemove',handler);
    cv.addEventListener('mouseleave',function(){$(tipId).classList.remove('show');$(crossId).style.display='none'});
  }
  /* Chart 1: Growth Over Time */
  attachChart('chart','chartCross1','chartTip1','_chart1',function(r){
    return '<div class="ct-label">'+MO[r.month-1]+' '+r.year+'</div>'+
      '<div class="ct-row"><span><span class="ct-dot" style="background:var(--accent)"></span>Portfolio</span><span style="color:var(--accent);font-weight:700;font-family:JetBrains Mono,monospace">$'+fmt(r.pv)+'</span></div>'+
      '<div class="ct-row"><span><span class="ct-dot" style="background:var(--text3)"></span>Invested</span><span style="color:var(--text2);font-family:JetBrains Mono,monospace">$'+fmt(r.tInv)+'</span></div>'+
      '<div class="ct-row"><span><span class="ct-dot" style="background:var(--text2)"></span>MM Return</span><span style="color:var(--text2);font-family:JetBrains Mono,monospace">$'+fmt(r.mmOnlyBal)+'</span></div>'+
      '<div class="ct-row" style="margin-top:4px;padding-top:4px;border-top:1px solid var(--border)"><span style="color:var(--text3)">Return</span><span style="color:'+(r.pv>=r.tInv?'var(--accent)':'var(--red)')+';font-weight:600;font-family:JetBrains Mono,monospace">'+((r.pv-r.tInv)/r.tInv*100).toFixed(1)+'%</span></div>';
  });
  /* Chart 2: Dividend Balance */
  attachChart('chart2','chartCross2','chartTip2','_chart2',function(r){
    const mmInt=r.divBal-r.tDiv;
    return '<div class="ct-label">'+MO[r.month-1]+' '+r.year+'</div>'+
      '<div class="ct-row"><span><span class="ct-dot" style="background:var(--gold)"></span>Div + MM</span><span style="color:var(--gold);font-weight:700;font-family:JetBrains Mono,monospace">$'+fmt(r.divBal)+'</span></div>'+
      '<div class="ct-row"><span><span class="ct-dot" style="background:var(--text3)"></span>Div Accumulated</span><span style="color:var(--text2);font-family:JetBrains Mono,monospace">$'+fmt(r.tDiv)+'</span></div>'+
      '<div class="ct-row" style="margin-top:4px;padding-top:4px;border-top:1px solid var(--border)"><span style="color:var(--text3)">MM Interest</span><span style="color:var(--accent);font-weight:600;font-family:JetBrains Mono,monospace">$'+fmt(mmInt)+'</span></div>'+
      '<div class="ct-row"><span style="color:var(--text3)">Rate</span><span style="color:var(--text2);font-family:JetBrains Mono,monospace">'+(r.mmRate*100).toFixed(2)+'% APR</span></div>';
  });
}

function renderTaxImpact(){
  const el=$('taxBody');if(!el||!window._bk)return;
  const bk=window._bk;
  let rate=parseFloat(($('taxRate')||{}).value)||30;
  rate=Math.max(0,Math.min(60,rate));

  /* Aggregate by year: dividends, MM interest, invested, end-of-year snapshots */
  const years={};
  bk.forEach(r=>{
    const y=r.year;
    if(!years[y])years[y]={divs:0,mmInt:0,invested:0,endPv:0,endDivBal:0,endTInv:0,months:0};
    years[y].divs+=r.divs;
    years[y].mmInt+=r.mmInt;
    years[y].invested+=r.invested;
    years[y].endPv=r.pv;
    years[y].endDivBal=r.divBal;
    years[y].endTInv=r.tInv;
    years[y].months++;
  });
  const yrs=Object.keys(years).sort();

  /* === Tax Detail Table === */
  let totalDivs=0,totalDivTax=0,totalInt=0,totalIntTax=0;
  let h='<h4 style="font-size:14px;font-weight:600;color:var(--text1);margin-bottom:10px">Tax Liability by Year</h4>';
  h+='<div style="overflow-x:auto"><table><thead><tr><th style="text-align:left">Year</th><th>Dividends</th><th>Tax on Dividends</th><th>MM Interest Earned</th><th>Tax on Interest</th><th>Total Taxes</th></tr></thead><tbody>';
  yrs.forEach(y=>{
    const d=years[y];
    const divTax=d.divs*rate/100;
    const intTax=d.mmInt*rate/100;
    totalDivs+=d.divs;totalDivTax+=divTax;totalInt+=d.mmInt;totalIntTax+=intTax;
    h+='<tr><td style="color:var(--text2)">'+y+'</td><td style="color:var(--gold)">$'+fmt(d.divs)+'</td><td style="color:var(--red)">$'+fmt(divTax)+'</td><td style="color:var(--accent)">$'+fmt(d.mmInt)+'</td><td style="color:var(--red)">$'+fmt(intTax)+'</td><td style="color:var(--red);font-weight:600">$'+fmt(divTax+intTax)+'</td></tr>';
  });
  h+='</tbody><tfoot><tr style="border-top:2px solid var(--border);font-weight:700"><td style="color:var(--text1)">Total</td><td style="color:var(--gold)">$'+fmt(totalDivs)+'</td><td style="color:var(--red)">$'+fmt(totalDivTax)+'</td><td style="color:var(--accent)">$'+fmt(totalInt)+'</td><td style="color:var(--red)">$'+fmt(totalIntTax)+'</td><td style="color:var(--red)">$'+fmt(totalDivTax+totalIntTax)+'</td></tr></tfoot></table></div>';
  h+='<div style="margin-top:8px;font-size:12px;color:var(--text3)">Tax rate: '+rate+'% applied to dividends in the year received and MM interest in the year earned.</div>';

  /* === Annual Return Table === */
  /* Build row data first so we can sort */
  let prevEndPv=0;
  const returnRows=[];
  yrs.forEach(y=>{
    const d=years[y];
    const divTax=d.divs*rate/100;
    const intTax=d.mmInt*rate/100;
    const stockVal=d.endPv;
    const portfolioVal=stockVal+d.endDivBal;
    const yearTax=divTax+intTax;
    const avgNewCapital=d.invested*0.542;
    const baseCapital=prevEndPv+avgNewCapital;
    const stockGain=stockVal-prevEndPv-d.invested;
    const totalGain=stockGain+d.divs+d.mmInt;
    const afterTaxGain=stockGain+(d.divs-divTax)+(d.mmInt-intTax);
    const preTaxRet=baseCapital>0?(totalGain/baseCapital*100):0;
    const afterTaxRet=baseCapital>0?(afterTaxGain/baseCapital*100):0;
    returnRows.push({year:y,invested:d.invested,divs:d.divs,mmInt:d.mmInt,stockVal,portfolioVal,yearTax,avgNewCapital,baseCapital,stockGain,totalGain,afterTaxGain,preTaxRet,afterTaxRet,prevEndPv,divTax,intTax});
    prevEndPv=stockVal;
  });
  /* Store for sort toggling */
  window._returnRows=returnRows;
  window._returnSortAsc=false; /* newest first by default */

  h+=buildReturnTable(returnRows,false);
  el.innerHTML=h;
}

/* Build Annual Return table HTML from row data */
function buildReturnTable(rows,sortAsc){
  const display=sortAsc?[...rows]:[...rows].reverse();
  const arrow=sortAsc?'▲':'▼';
  let h='<h4 style="font-size:14px;font-weight:600;color:var(--text1);margin:24px 0 10px">Annual Portfolio Return</h4>';
  h+='<div style="overflow-x:auto"><table><thead><tr><th style="text-align:left;cursor:pointer" onclick="toggleReturnSort()" id="thRetYear">Year '+arrow+'</th><th>Invested</th><th>Dividends</th><th>MM Interest</th><th>Stock Value<span class="col-info">*<span class="col-tooltip">Shares held × December closing price</span></span></th><th>Portfolio Value<span class="col-info">*<span class="col-tooltip">Stock Value + accumulated dividend balance (dividends + MM interest)</span></span></th><th>Pre-Tax Return<span class="col-info">*<span class="col-tooltip">Return = (stock gain + dividends + MM interest) ÷ (beginning stock value + avg invested capital)</span></span></th></tr></thead><tbody>';

  display.forEach(r=>{
    const retColor=r.preTaxRet>=0?'var(--accent)':'var(--red)';
    h+='<tr><td style="color:var(--text2)">'+r.year+'</td>';
    h+='<td>$'+fmt(r.invested)+'</td>';
    h+='<td style="color:var(--gold)">$'+fmt(r.divs)+'</td>';
    h+='<td style="color:var(--accent)">$'+fmt(r.mmInt)+'</td>';
    h+='<td class="clickable-cell" onclick="showReturnCalc(\''+r.year+'\',\'stockVal\')" title="Click to see calculation">$'+fmt(r.stockVal)+'</td>';
    h+='<td class="clickable-cell" onclick="showReturnCalc(\''+r.year+'\',\'portfolioVal\')" style="font-weight:600" title="Click to see calculation">$'+fmt(r.portfolioVal)+'</td>';
    h+='<td class="clickable-cell" onclick="showReturnCalc(\''+r.year+'\',\'preTaxRet\')" style="color:'+retColor+';font-weight:600" title="Click to see calculation">'+(r.preTaxRet>=0?'+':'')+r.preTaxRet.toFixed(1)+'%</td>';
    h+='</tr>';
  });
  h+='</tbody></table></div>';
  h+='<div style="margin-top:8px;font-size:12px;color:var(--text3)">Click any highlighted cell for calculation details. Avg invested capital ≈ year\'s contributions × 0.542 (DCA mid-year approximation).</div>';
  return h;
}

/* Toggle annual return table sort order */
function toggleReturnSort(){
  window._returnSortAsc=!window._returnSortAsc;
  const container=$('taxBody');if(!container||!window._returnRows)return;
  /* Find and replace just the annual return section */
  const newHtml=buildReturnTable(window._returnRows,window._returnSortAsc);
  /* The annual return section starts after the tax footnote div */
  const parts=container.innerHTML.split('<h4 style="font-size:14px;font-weight:600;color:var(--text1);margin:24px 0 10px">Annual Portfolio Return</h4>');
  if(parts.length===2){
    container.innerHTML=parts[0]+newHtml;
  }
}

/* Show calculation detail modal for annual return table cells */
function showReturnCalc(year,field){
  if(!window._returnRows)return;
  const r=window._returnRows.find(x=>x.year===year);
  if(!r)return;
  let h='';
  const fmtV=n=>'$'+fmt(n);
  const pctV=n=>(n>=0?'+':'')+n.toFixed(2)+'%';

  if(field==='stockVal'){
    $('modalTitle').textContent=year+' — Stock Value';
    $('modalSub').textContent='End-of-year holdings value';
    h+='<div class="detail-row"><div><div class="d-sym">Formula</div><div class="d-name">Total shares held × December closing price</div></div></div>';
    h+='<div class="detail-total"><div class="dt-label">Stock Value</div><div class="dt-val" style="color:var(--accent)">'+fmtV(r.stockVal)+'</div></div>';
  }

  else if(field==='portfolioVal'){
    $('modalTitle').textContent=year+' — Portfolio Value';
    $('modalSub').textContent='Stock value + accumulated dividend balance';
    h+='<div class="detail-row"><div><div class="d-sym" style="color:var(--accent)">Stock Value</div><div class="d-name">Shares held × December close price</div></div><div class="d-nums"><div class="d-val">'+fmtV(r.stockVal)+'</div></div></div>';
    h+='<div class="detail-row"><div><div class="d-sym" style="color:var(--gold)">Dividend Balance</div><div class="d-name">Accumulated dividends + MM interest earned on cash</div></div><div class="d-nums"><div class="d-val" style="color:var(--gold)">'+fmtV(r.portfolioVal-r.stockVal)+'</div></div></div>';
    h+='<div class="detail-total" style="background:var(--accent-dim);border-color:rgba(16,185,129,.25)"><div><div class="dt-label" style="color:var(--accent)">Portfolio Value</div><div style="font-size:11px;color:var(--text2);margin-top:1px">'+fmtV(r.stockVal)+' + '+fmtV(r.portfolioVal-r.stockVal)+'</div></div><div class="dt-val" style="color:var(--accent)">'+fmtV(r.portfolioVal)+'</div></div>';
  }

  else if(field==='afterTax'){
    const afterTaxVal=r.portfolioVal-r.yearTax;
    $('modalTitle').textContent=year+' — After-Tax Value';
    $('modalSub').textContent='Portfolio value minus taxes on this year\'s income';
    h+='<div class="detail-row"><div><div class="d-sym" style="color:var(--accent)">Portfolio Value</div><div class="d-name">Stock value + dividend balance</div></div><div class="d-nums"><div class="d-val">'+fmtV(r.portfolioVal)+'</div></div></div>';
    h+='<div class="detail-row"><div><div class="d-sym" style="color:var(--red)">Tax on Dividends</div><div class="d-name">'+fmtV(r.divs)+' × '+((r.divTax/Math.max(r.divs,0.01))*100).toFixed(0)+'%</div></div><div class="d-nums"><div class="d-val" style="color:var(--red)">−'+fmtV(r.divTax)+'</div></div></div>';
    h+='<div class="detail-row"><div><div class="d-sym" style="color:var(--red)">Tax on MM Interest</div><div class="d-name">'+fmtV(r.mmInt)+' × '+((r.intTax/Math.max(r.mmInt,0.01))*100).toFixed(0)+'%</div></div><div class="d-nums"><div class="d-val" style="color:var(--red)">−'+fmtV(r.intTax)+'</div></div></div>';
    h+='<div class="detail-total"><div><div class="dt-label">After-Tax Value</div><div style="font-size:11px;color:var(--text2);margin-top:1px">'+fmtV(r.portfolioVal)+' − '+fmtV(r.yearTax)+' taxes</div></div><div class="dt-val" style="color:var(--accent)">'+fmtV(afterTaxVal)+'</div></div>';
  }

  else if(field==='preTaxRet'){
    $('modalTitle').textContent=year+' — Pre-Tax Return';
    $('modalSub').textContent='Total gain ÷ capital base';
    h+='<div class="section-label">Numerator (Total Gain)</div>';
    h+='<div class="detail-row"><div><div class="d-sym">Stock Gain</div><div class="d-name">End stock value − beginning stock value − new investment</div></div><div class="d-nums"><div class="d-val" style="color:'+(r.stockGain>=0?'var(--accent)':'var(--red)')+'">'+fmtV(r.stockGain)+'</div><div class="d-sub">'+fmtV(r.stockVal)+' − '+fmtV(r.prevEndPv)+' − '+fmtV(r.invested)+'</div></div></div>';
    h+='<div class="detail-row"><div><div class="d-sym" style="color:var(--gold)">Dividends</div><div class="d-name">Cash dividends received this year</div></div><div class="d-nums"><div class="d-val" style="color:var(--gold)">'+fmtV(r.divs)+'</div></div></div>';
    h+='<div class="detail-row"><div><div class="d-sym" style="color:var(--accent)">MM Interest</div><div class="d-name">Money market interest earned this year</div></div><div class="d-nums"><div class="d-val" style="color:var(--accent)">'+fmtV(r.mmInt)+'</div></div></div>';
    h+='<div class="detail-total" style="background:var(--accent-dim);border-color:rgba(16,185,129,.25)"><div class="dt-label" style="color:var(--accent)">Total Gain</div><div class="dt-val" style="color:var(--accent)">'+fmtV(r.totalGain)+'</div></div>';
    h+='<div class="section-label" style="margin-top:16px">Denominator (Capital Base)</div>';
    h+='<div class="detail-row"><div><div class="d-sym">Beginning Stock Value</div><div class="d-name">Prior year\'s ending stock value</div></div><div class="d-nums"><div class="d-val">'+fmtV(r.prevEndPv)+'</div></div></div>';
    h+='<div class="detail-row"><div><div class="d-sym">Avg Invested Capital</div><div class="d-name">'+fmtV(r.invested)+' × 0.542 (DCA mid-year approx)</div></div><div class="d-nums"><div class="d-val">'+fmtV(r.avgNewCapital)+'</div></div></div>';
    h+='<div class="detail-total"><div class="dt-label">Capital Base</div><div class="dt-val">'+fmtV(r.baseCapital)+'</div></div>';
    h+='<div style="margin-top:14px;padding:12px;background:var(--bg);border:1px solid var(--border);border-radius:8px;font-size:13px;font-family:JetBrains Mono,monospace;color:var(--text2)">Pre-Tax Return = '+fmtV(r.totalGain)+' ÷ '+fmtV(r.baseCapital)+' = <span style="color:'+(r.preTaxRet>=0?'var(--accent)':'var(--red)')+';font-weight:700">'+pctV(r.preTaxRet)+'</span></div>';
  }

  else if(field==='afterTaxRet'){
    $('modalTitle').textContent=year+' — After-Tax Return';
    $('modalSub').textContent='After-tax gain ÷ capital base';
    h+='<div class="section-label">Numerator (After-Tax Gain)</div>';
    h+='<div class="detail-row"><div><div class="d-sym">Stock Gain</div><div class="d-name">Price appreciation (not taxed until sold)</div></div><div class="d-nums"><div class="d-val" style="color:'+(r.stockGain>=0?'var(--accent)':'var(--red)')+'">'+fmtV(r.stockGain)+'</div><div class="d-sub">'+fmtV(r.stockVal)+' − '+fmtV(r.prevEndPv)+' − '+fmtV(r.invested)+'</div></div></div>';
    h+='<div class="detail-row"><div><div class="d-sym" style="color:var(--gold)">After-Tax Dividends</div><div class="d-name">'+fmtV(r.divs)+' − '+fmtV(r.divTax)+' tax</div></div><div class="d-nums"><div class="d-val" style="color:var(--gold)">'+fmtV(r.divs-r.divTax)+'</div></div></div>';
    h+='<div class="detail-row"><div><div class="d-sym" style="color:var(--accent)">After-Tax MM Interest</div><div class="d-name">'+fmtV(r.mmInt)+' − '+fmtV(r.intTax)+' tax</div></div><div class="d-nums"><div class="d-val" style="color:var(--accent)">'+fmtV(r.mmInt-r.intTax)+'</div></div></div>';
    h+='<div class="detail-total" style="background:var(--accent-dim);border-color:rgba(16,185,129,.25)"><div class="dt-label" style="color:var(--accent)">After-Tax Gain</div><div class="dt-val" style="color:var(--accent)">'+fmtV(r.afterTaxGain)+'</div></div>';
    h+='<div class="section-label" style="margin-top:16px">Denominator (Capital Base)</div>';
    h+='<div class="detail-row"><div><div class="d-sym">Beginning Stock Value</div><div class="d-name">Prior year\'s ending stock value</div></div><div class="d-nums"><div class="d-val">'+fmtV(r.prevEndPv)+'</div></div></div>';
    h+='<div class="detail-row"><div><div class="d-sym">Avg Invested Capital</div><div class="d-name">'+fmtV(r.invested)+' × 0.542 (DCA mid-year approx)</div></div><div class="d-nums"><div class="d-val">'+fmtV(r.avgNewCapital)+'</div></div></div>';
    h+='<div class="detail-total"><div class="dt-label">Capital Base</div><div class="dt-val">'+fmtV(r.baseCapital)+'</div></div>';
    h+='<div style="margin-top:14px;padding:12px;background:var(--bg);border:1px solid var(--border);border-radius:8px;font-size:13px;font-family:JetBrains Mono,monospace;color:var(--text2)">After-Tax Return = '+fmtV(r.afterTaxGain)+' ÷ '+fmtV(r.baseCapital)+' = <span style="color:'+(r.afterTaxRet>=0?'var(--accent)':'var(--red)')+';font-weight:700">'+pctV(r.afterTaxRet)+'</span></div>';
  }

  $('modalBody').innerHTML=h;
  $('modalOverlay').classList.add('show');
}

renderAmts();renderYrs();updBudget();renderAlloc();

// No-auth mode: welcome guide auto-shown, dismissWelcomeGuide calls loadTickers()
