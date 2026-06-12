(function () {
  const panel = document.querySelector("[data-chat-kind][data-room-id]");
  if (!panel) return;

  const list = document.getElementById("message-list");
  const form = document.querySelector("[data-chat-form]");
  const input = form ? form.querySelector("input[name='content']") : null;

  function appendMessage(message) {
    const row = document.createElement("article");
    row.className = "message-row";
    row.id = `message-${message.id || Date.now()}`;
    const media = [
      message.image ? `<img class="message-media" src="${message.image}" alt="zalaczony obraz">` : "",
      message.audio ? `<audio controls src="${message.audio}"></audio>` : "",
    ].join("");
    row.innerHTML = `
      <div class="avatar">${escapeHtml(message.author.slice(0, 1).toUpperCase())}</div>
      <div class="message-body">
        <div class="message-meta"><strong>${escapeHtml(message.author)}</strong><time>${escapeHtml(message.created_at || "")}</time></div>
        ${message.content ? `<p>${escapeHtml(message.content)}</p>` : ""}
        ${media}
      </div>`;
    list.appendChild(row);
    list.scrollTop = list.scrollHeight;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (char) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char];
    });
  }

  const wsScheme = window.location.protocol === "https:" ? "wss" : "ws";
  const kind = panel.dataset.chatKind;
  const roomId = panel.dataset.roomId;
  const socket = new WebSocket(`${wsScheme}://${window.location.host}/ws/${kind}/${roomId}/`);

  socket.onmessage = function (event) {
    appendMessage(JSON.parse(event.data));
  };

  if (!form || !input) return;

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    const hasFile = Array.from(form.querySelectorAll("input[type='file']")).some((field) => field.files.length);
    const content = input.value.trim();

    if (!hasFile && content && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ content }));
      input.value = "";
      return;
    }

    const response = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });

    if (response.ok) {
      appendMessage(await response.json());
      form.reset();
    }
  });
})();

(function () {
  const panel = document.querySelector("[data-voice-channel]");
  if (!panel) return;

  const joinButton = document.querySelector("[data-voice-join]");
  const muteButton = document.querySelector("[data-voice-mute]");
  const leaveButton = document.querySelector("[data-voice-leave]");
  const localState = document.querySelector("[data-local-state]");
  const remoteName = document.querySelector("[data-remote-name]");
  const remoteState = document.querySelector("[data-remote-state]");
  const remoteAudio = document.querySelector("[data-remote-audio]");
  const wsScheme = window.location.protocol === "https:" ? "wss" : "ws";
  const channelId = panel.dataset.voiceChannel;

  let socket = null;
  let peer = null;
  let localStream = null;
  let muted = false;

  function setStatus(text) {
    if (localState) localState.textContent = text;
  }

  function setRemote(name, text) {
    if (name && remoteName) remoteName.textContent = name;
    if (remoteState) remoteState.textContent = text;
  }

  function send(payload) {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(payload));
    }
  }

  async function ensurePeer() {
    if (peer) return peer;
    peer = new RTCPeerConnection({ iceServers: [{ urls: "stun:stun.l.google.com:19302" }] });
    localStream.getTracks().forEach((track) => peer.addTrack(track, localStream));
    peer.ontrack = function (event) {
      remoteAudio.srcObject = event.streams[0];
      setRemote(null, "Polaczono");
    };
    peer.onicecandidate = function (event) {
      if (event.candidate) send({ type: "ice-candidate", candidate: event.candidate });
    };
    peer.onconnectionstatechange = function () {
      if (peer.connectionState === "disconnected" || peer.connectionState === "failed") {
        setRemote(null, "Rozlaczono");
      }
    };
    return peer;
  }

  async function makeOffer() {
    const pc = await ensurePeer();
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    send({ type: "offer", sdp: offer });
  }

  async function handleSignal(message) {
    if (message.type === "user-joined") {
      setRemote(message.from, "Dołącza");
      if (localStream) await makeOffer();
      return;
    }

    if (message.type === "user-left") {
      setRemote(message.from, "Opuscil kanal");
      return;
    }

    if (message.type === "offer") {
      setRemote(message.from, "Laczenie");
      const pc = await ensurePeer();
      await pc.setRemoteDescription(new RTCSessionDescription(message.sdp));
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      send({ type: "answer", sdp: answer });
      return;
    }

    if (message.type === "answer") {
      const pc = await ensurePeer();
      await pc.setRemoteDescription(new RTCSessionDescription(message.sdp));
      setRemote(message.from, "Polaczono");
      return;
    }

    if (message.type === "ice-candidate" && message.candidate) {
      const pc = await ensurePeer();
      await pc.addIceCandidate(new RTCIceCandidate(message.candidate));
    }
  }

  async function joinVoice() {
    try {
      localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      socket = new WebSocket(`${wsScheme}://${window.location.host}/ws/voice/${channelId}/`);
      socket.onopen = function () {
        setStatus("Na kanale");
        joinButton.disabled = true;
        muteButton.disabled = false;
        leaveButton.disabled = false;
      };
      socket.onmessage = async function (event) {
        await handleSignal(JSON.parse(event.data));
      };
      socket.onclose = function () {
        setStatus("Rozlaczony");
      };
    } catch (error) {
      setStatus("Brak dostepu do mikrofonu");
    }
  }

  function leaveVoice() {
    if (socket) socket.close();
    if (peer) peer.close();
    if (localStream) localStream.getTracks().forEach((track) => track.stop());
    socket = null;
    peer = null;
    localStream = null;
    muted = false;
    setStatus("Rozlaczony");
    setRemote("Drugi uzytkownik", "Oczekiwanie na druga osobe");
    joinButton.disabled = panel.dataset.voiceAllowed !== "1";
    muteButton.disabled = true;
    leaveButton.disabled = true;
    muteButton.textContent = "Wycisz mikrofon";
  }

  if (!joinButton || !muteButton || !leaveButton || panel.dataset.voiceAllowed !== "1") return;

  joinButton.addEventListener("click", joinVoice);
  leaveButton.addEventListener("click", leaveVoice);
  muteButton.addEventListener("click", function () {
    if (!localStream) return;
    muted = !muted;
    localStream.getAudioTracks().forEach((track) => {
      track.enabled = !muted;
    });
    muteButton.textContent = muted ? "Wlacz mikrofon" : "Wycisz mikrofon";
    setStatus(muted ? "Wyciszony" : "Na kanale");
  });
})();
