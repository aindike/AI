// ==================== VSCode Workspace UI Logic ====================
let vscodeOpenTabs = [];
let vscodeActiveTab = null;
let vscodeCurrentWorkspace = null;
require.config({ paths: { 'vs': 'https://cdn.jsdelivr.net/npm/monaco-editor@0.46.0/min/vs' } });

window.loadVSCodeWorkspaceUI = async function(project) {
  vscodeCurrentWorkspace = project;
  document.querySelector("main").classList.add("hidden");
  document.getElementById("main-app-ui").classList.add("hidden");
  document.getElementById("vscode-workspace-ui").classList.remove("hidden");

  // Load file list
  const res = await fetch(`/api/plugin_files/${project}`).then(r=>r.json());
  const pfList = document.getElementById('vscode-plugin-file-list');
  pfList.innerHTML = '';
  (res.files||[]).forEach(f=>{
    const li = document.createElement('li');
    li.textContent = f;
    li.className = "px-2 py-1 rounded hover:bg-gray-800 cursor-pointer text-gray-100";
    li.onclick = ()=>vscodeOpenFileTab(project, f);
    pfList.appendChild(li);
  });

  // Reset tabs and editor
  vscodeOpenTabs = [];
  vscodeActiveTab = null;
  document.getElementById('vscode-tab-bar').innerHTML = '';
  if(window.vscodeEditor) window.vscodeEditor.setValue('');
  document.getElementById('vscode-chat-history').innerHTML = '';
};

document.getElementById("back-btn").onclick = () => {
  document.getElementById("vscode-workspace-ui").classList.add("hidden");
  document.querySelector("main").classList.remove("hidden");
  document.getElementById("main-app-ui").classList.remove("hidden");
  vscodeCurrentWorkspace = null;
};

function vscodeOpenFileTab(ws, filename){
  let tab = vscodeOpenTabs.find(t=>t.filename===filename);
  if(tab){
    vscodeSetActiveTab(tab);
    return;
  }
  fetch(`/api/plugin_file/${ws}/${filename}`).then(r=>r.json()).then(data=>{
    require(['vs/editor/editor.main'], function () {
      const model = monaco.editor.createModel(data.content || '', "csharp");
      tab = { filename, model };
      vscodeOpenTabs.push(tab);
      vscodeSetActiveTab(tab);
      vscodeRenderTabs();
    });
  });
}
function vscodeSetActiveTab(tab){
  vscodeActiveTab = tab;
  vscodeRenderTabs();
  if(window.vscodeEditor){
    window.vscodeEditor.setModel(tab.model);
    monaco.editor.setTheme("vs-dark"); // force dark theme
  }else{
    require(['vs/editor/editor.main'], function () {
      window.vscodeEditor = monaco.editor.create(document.getElementById('vscode-editor'), {
        model: tab.model,
        theme: "vs-dark", // << IMPORTANT!
        language: "csharp",
        automaticLayout:true,
        fontSize:15,
        fontFamily: "Fira Mono, Menlo, Monaco, 'Courier New', monospace",
        minimap: {enabled: false}
      });
      monaco.editor.setTheme("vs-dark"); // extra safe!
    });
  }
}
function vscodeRenderTabs(){
  const tabBar = document.getElementById('vscode-tab-bar');
  tabBar.innerHTML = '';
  vscodeOpenTabs.forEach(tab=>{
    const div = document.createElement('div');
    div.className = 'tab flex items-center px-4 py-1 cursor-pointer' + (tab===vscodeActiveTab ? ' tab-active' : '');
    div.textContent = tab.filename;
    div.onclick = ()=>vscodeSetActiveTab(tab);
    // close btn
    const close = document.createElement('span');
    close.className = 'tab-close ml-2';
    close.innerHTML = '&times;';
    close.onclick = (e)=>{
      e.stopPropagation();
      vscodeCloseTab(tab);
    };
    div.appendChild(close);
    tabBar.appendChild(div);
  });
  // Save button for current tab
  if(vscodeActiveTab){
    const saveBtn = document.createElement('button');
    saveBtn.className = "ml-4 px-3 py-1 rounded bg-blue-700 text-white text-xs";
    saveBtn.textContent = "Save";
    saveBtn.onclick = ()=>vscodeSaveActiveTab();
    tabBar.appendChild(saveBtn);
  }
}
function vscodeCloseTab(tab){
  let idx = vscodeOpenTabs.indexOf(tab);
  if(idx > -1){
    vscodeOpenTabs.splice(idx,1);
    if(vscodeActiveTab===tab){
      vscodeActiveTab = vscodeOpenTabs[idx] || vscodeOpenTabs[idx-1] || null;
      if(vscodeActiveTab && window.vscodeEditor) window.vscodeEditor.setModel(vscodeActiveTab.model);
      else if(window.vscodeEditor) window.vscodeEditor.setValue('');
    }
    vscodeRenderTabs();
  }
}
function vscodeSaveActiveTab(){
  if(!vscodeActiveTab || !vscodeCurrentWorkspace) return;
  fetch(`/api/plugin_file/${vscodeCurrentWorkspace}/${vscodeActiveTab.filename}`, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({content:vscodeActiveTab.model.getValue()})
  }).then(r=>r.json()).then(()=>{
    vscodeAppendChat("bot", `💾 Saved ${vscodeActiveTab.filename}`);
  });
}

// Chat for VSCode UI
document.getElementById('vscode-chat-form').onsubmit = async (e)=>{
  e.preventDefault();
  const msg = document.getElementById('vscode-msg-input').value.trim();
  if(!msg || !vscodeCurrentWorkspace) return;
  vscodeAppendChat("user", msg);
  document.getElementById('vscode-msg-input').value = "";
  const res = await fetch('/chat',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({message:msg, history:[], project:vscodeCurrentWorkspace})
  }).then(r=>r.json());
  vscodeAppendChat("bot", res.reply || "");
};
function vscodeAppendChat(who, txt){
  const chatHistory = document.getElementById('vscode-chat-history');
  const bubble = document.createElement('div');
  bubble.className = (who==="user"?"text-right text-blue-300":"text-left text-gray-300") + " my-1";
  bubble.innerHTML = txt;
  chatHistory.appendChild(bubble);
  chatHistory.scrollTop = chatHistory.scrollHeight;
}
