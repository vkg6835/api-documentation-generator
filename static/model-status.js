'use strict';
let modelRefreshTimer;

function updateModelStatus() {
  const status=state.health?.llm;
  const pill=document.getElementById('model-status');
  const notice=document.getElementById('model-notice');
  const unavailable=!status?.available;
  const busy=Boolean(status?.busy);
  pill.textContent=!status?'Checking local model…':busy?'Drafting descriptions…':status.available?status.model+' ready':status.state==='missing_model'?'Model missing':'Ollama unavailable';
  pill.className='status-pill'+(unavailable?' warning':busy?' busy':'');
  notice.hidden=!status || (status.available && !busy);
  if (status) notice.innerHTML=`<div><strong>${h(status.message || (unavailable?'Local generation is unavailable.':'The local model is drafting descriptions.'))}</strong><p>${h(status.action || '')}</p></div><button class="button small" id="recheck-model">Recheck model</button>`;
  document.querySelectorAll('[data-model-action]').forEach(button=>{
    button.disabled=unavailable || busy || state.project?.job?.status==='running';
    button.title=unavailable?(status?.action || 'Checking the local model.'):busy?'Wait for the current generation to finish.':'';
  });
}

async function refreshModelStatus() {
  try { state.health=await api('/api/health'); }
  catch (error) { state.health={llm:{available:false,state:'unavailable',message:'Cannot reach the local application.',action:'Keep the demo terminal open, then select Recheck model.'}}; }
  updateModelStatus();
  return state.health.llm;
}

function scheduleModelRefresh() {
  clearTimeout(modelRefreshTimer);
  modelRefreshTimer=setTimeout(async()=>{await refreshModelStatus();scheduleModelRefresh();},5000);
}
