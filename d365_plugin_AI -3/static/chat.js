// --- Helper for pretty chat bubbles ---
const wsHistoryBox = document.getElementById("project-chat-history");
const wsInput      = document.getElementById("project-create-input");

function wsBubble(txt, who){
  const outer = document.createElement("div");
  outer.className = "flex items-end mb-3 " + (who==="user" ? "justify-end" : "");
  let avatar, bubble;
  if(who==="user"){
    bubble = document.createElement("div");
    bubble.className="bubble-user px-4 py-2 rounded-2xl mr-1";
    bubble.textContent=txt;
    avatar = document.createElement("div");
    avatar.className="avatar-user";
    avatar.textContent="Me";
    outer.appendChild(bubble);
    outer.appendChild(avatar);
  }else{
    avatar = document.createElement("div");
    avatar.className="avatar-bot";
    avatar.textContent="Hi";
    bubble = document.createElement("div");
    bubble.className="bubble-bot px-4 py-2 rounded-2xl ml-1";
    bubble.innerHTML = txt;
    outer.appendChild(avatar);
    outer.appendChild(bubble);
  }
  return outer;
}

// --- Workspace list ---
async function loadProjects(){
  const res = await fetch("/projects").then(r=>r.json());
  const grid = document.getElementById("workspace-list");
  grid.innerHTML="";
  (res.projects||[]).forEach(p=>{
    const li = document.createElement("li");
    li.className="card cursor-pointer p-4 text-center hover:ring-2 hover:ring-black/40";
    li.textContent=p;
    li.onclick=()=>selectProject(p);
    grid.appendChild(li);
  });
}
loadProjects();

// --- Mini-chat for project creation ---
document.getElementById("project-create-form").onsubmit=async e=>{
  e.preventDefault();
  const text = wsInput.value.trim();
  if(!text) return;
  wsHistoryBox.appendChild(wsBubble(text,"user"));
  wsInput.value="";
  const typing = wsBubble("…","bot"); wsHistoryBox.appendChild(typing);
  wsHistoryBox.scrollTop = wsHistoryBox.scrollHeight;

  const data = await fetch("/chat",{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({message:text,history:[]})
  }).then(r=>r.json()).catch(err=>({reply:"Error: "+err}));

  typing.remove();
  wsHistoryBox.appendChild(wsBubble(data.reply,"bot"));
  wsHistoryBox.scrollTop = wsHistoryBox.scrollHeight;
  await loadProjects();                      // refresh list
};

// --- Agent chat state & helpers ---
let currentProject = null;
let fullHistory = [];

// --- Agent chat UI render ---
const chatHistory=document.getElementById("chat-history");
const chatForm=document.getElementById("chat-form");
const msgInput=document.getElementById("msg-input");

function renderAgentHistory(){
  chatHistory.innerHTML="";
  fullHistory.forEach(m=>{
    const b=wsBubble(m.content,m.role==="user"?"user":"bot");
    chatHistory.appendChild(b);
  });
  chatHistory.scrollTop=99999;
}

// --- Select project & reset agent chat ---
function selectProject(p){
  currentProject = p;
  document.getElementById("current-project-label").textContent = "Workspace – " + p;
  document.querySelector("main").classList.add("hidden");
  document.getElementById("main-app-ui").classList.remove("hidden");
   // Show VSCode-style workspace UI:
  document.getElementById("vscode-workspace-ui").classList.remove("hidden");

  // Call new workspace loader (from vscode_workspace.js):
  if (window.loadVSCodeWorkspaceUI) {
    window.loadVSCodeWorkspaceUI(p);
  }
  // Reset agent chat history on every project selection!
  fullHistory = [
    { role: "assistant", content: "👋 Hi! Ask me to create, build, deploy, or manage your plugin projects!" }
  ];
  renderAgentHistory();

  // Optional: clear input field
  msgInput.value = "";
}

// --- Back to workspace: clear chat UI ---
document.getElementById("change-workspace-btn").onclick = () => {
  currentProject = null;
  document.getElementById("main-app-ui").classList.add("hidden");
  document.querySelector("main").classList.remove("hidden");
  msgInput.value = "";
};

// --- Send message with project context ---
chatForm.addEventListener("submit", async e => {
  e.preventDefault();
  if (!currentProject) return;
  const txt = msgInput.value.trim();
  if (!txt) return;

  // Always start fresh if history somehow empty (should never happen, but safe)
  if (!fullHistory.length) {
    fullHistory = [
      { role: "assistant", content: "👋 Hi! Ask me to create, build, deploy, or manage your plugin projects!" }
    ];
    renderAgentHistory();
  }

  fullHistory.push({ role: "user", content: txt });
  renderAgentHistory();
  msgInput.value = "";

  const typing = wsBubble("…", "bot");
  chatHistory.appendChild(typing);

  const data = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: txt,
      history: fullHistory,
      project: currentProject 
    })
  }).then(r => r.json()).catch(err => ({ reply: "Error: " + err }));

  typing.remove();
  fullHistory.push({ role: "assistant", content: data.reply });
  renderAgentHistory();
});
// --- Azure DevOps Modal Logic ---
let azdoProjects = {};
function showAzdoModal() {
  fetch("/azdo_projects")
    .then(r => r.json())
    .then(data => {
      azdoProjects = data.azdo_projects;
      const select = document.getElementById("azdo-project-select");
      select.innerHTML = "";
      Object.keys(azdoProjects).forEach(proj => {
        const opt = document.createElement("option");
        opt.value = proj;
        opt.textContent = proj;
        select.appendChild(opt);
      });
      document.getElementById("azdo-modal").classList.remove("hidden");
    });
}
document.getElementById("azdo-cancel-btn").onclick = () =>
  document.getElementById("azdo-modal").classList.add("hidden");
document.getElementById("azdo-push-btn").onclick = () => {
  const proj = document.getElementById("azdo-project-select").value;
  document.getElementById("azdo-modal").classList.add("hidden");
  fetch("/chat", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      message: "Push this project to Azure DevOps",
      history: [],  // or your real chat history
      project: currentProject,
      azdo_project: proj
    })
  })
  .then(r => r.json())
  .then(data => alert(data.reply)); // or display in chat
};
// --- Plugin File List and Editor Logic ---
async function loadPluginFiles(project) {
  const res = await fetch(`/api/plugin_files/${project}`).then(r=>r.json());
  const list = document.getElementById("plugin-file-list");
  list.innerHTML = "";
  (res.files || []).forEach(f => {
    const li = document.createElement("li");
    li.textContent = f;
    li.className = "cursor-pointer text-blue-700 hover:underline";
    li.onclick = () => openPluginFile(project, f);
    list.appendChild(li);
  });
  // Hide editor on new project selection
  document.getElementById("file-edit-container").classList.add("hidden");
}
async function openPluginFile(project, filename) {
  const res = await fetch(`/api/plugin_file/${project}/${filename}`).then(r=>r.json());
  document.getElementById("file-editor").value = res.content || "";
  document.getElementById("editing-file-label").textContent = filename;
  document.getElementById("file-edit-container").classList.remove("hidden");
  document.getElementById("save-file-btn").onclick = async () => {
    const newContent = document.getElementById("file-editor").value;
    await fetch(`/api/plugin_file/${project}/${filename}`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({content: newContent})
    });
    alert("File saved!");
    // Optional: notify agent
    // fullHistory.push({role:"user",content:`I have updated file ${filename}.`});
    // renderAgentHistory();
  };
  document.getElementById("close-file-btn").onclick = () => {
    document.getElementById("file-edit-container").classList.add("hidden");
  };
}

// When project is selected, load files (add to your selectProject function)
const originalSelectProject = selectProject;
selectProject = function(p) {
  originalSelectProject(p);
  loadPluginFiles(p);
}

