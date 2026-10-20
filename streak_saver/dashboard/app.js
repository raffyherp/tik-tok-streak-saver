const list = document.querySelector('#friendList');
const empty = document.querySelector('#emptyState');
const toast = document.querySelector('#toast');

function notify(message, error = false) {
  toast.textContent = message;
  toast.className = `toast show${error ? ' error' : ''}`;
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => toast.className = 'toast', 5000);
}

async function request(path, options = {}) {
  const response = await fetch(path, {headers: {'Content-Type': 'application/json'}, ...options});
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request gagal (${response.status})`);
  return body;
}

function friendRow(friend = {}) {
  const row = document.createElement('div');
  row.className = 'friend-row';
  row.innerHTML = `
    <input class="enabled" type="checkbox" ${friend.enabled ? 'checked' : ''} aria-label="Aktifkan teman">
    <input class="username" type="text" maxlength="80" placeholder="username / nama percakapan">
    <input class="message" type="text" maxlength="500" placeholder="Kosong = pakai pesan default">
    <button class="remove" title="Hapus" aria-label="Hapus">×</button>`;
  row.querySelector('.username').value = friend.username || '';
  row.querySelector('.message').value = friend.message || '';
  row.querySelector('.remove').onclick = () => { row.remove(); updateEmpty(); };
  list.append(row);
  updateEmpty();
}

function updateEmpty() { empty.classList.toggle('visible', list.children.length === 0); }

function collectFriends() {
  return [...list.querySelectorAll('.friend-row')].map(row => ({
    enabled: row.querySelector('.enabled').checked,
    username: row.querySelector('.username').value.trim(),
    message: row.querySelector('.message').value.trim(),
  })).filter(friend => friend.username);
}

async function load() {
  try {
    const state = await request('/api/state');
    document.querySelector('#defaultMessage').value = state.default_message;
    document.querySelector('#scheduleText').textContent = state.schedule + (state.last_send ? ` · terakhir ${state.last_send}` : '');
    document.querySelector('#cookieStatus').textContent = state.cookie_ready ? 'Cookie TikTok siap' : 'Cookie belum ada';
    document.querySelector('#statusDot').classList.toggle('ready', state.cookie_ready);
    const selected = new Map(state.friends.map(friend => [friend.username, friend]));
    const names = [...new Set([...selected.keys(), ...state.discovered])];
    names.forEach(name => friendRow(selected.get(name) || {username: name, message: '', enabled: false}));
    updateEmpty();
  } catch (error) { notify(error.message, true); }
}

document.querySelector('#addButton').onclick = () => friendRow({enabled: true});

document.querySelector('#scanButton').onclick = async event => {
  const button = event.currentTarget;
  button.disabled = true; button.textContent = 'Memindai…';
  try {
    const data = await request('/api/discover', {method: 'POST'});
    const existing = new Set(collectFriends().map(friend => friend.username));
    data.friends.filter(name => !existing.has(name)).forEach(name => friendRow({username: name, enabled: false}));
    notify(`${data.friends.length} percakapan ditemukan.`);
  } catch (error) { notify(error.message, true); }
  finally { button.disabled = false; button.textContent = '↻ Scan TikTok'; }
};

document.querySelector('#saveButton').onclick = async event => {
  const button = event.currentTarget; button.disabled = true;
  try {
    const data = await request('/api/settings', {method: 'POST', body: JSON.stringify({
      default_message: document.querySelector('#defaultMessage').value.trim(), friends: collectFriends(),
    })});
    notify(`${data.saved} teman aktif tersimpan.`);
  } catch (error) { notify(error.message, true); }
  finally { button.disabled = false; }
};

document.querySelector('#sendButton').onclick = async event => {
  if (!confirm('Kirim pesan sekarang ke semua teman yang dicentang?')) return;
  const button = event.currentTarget; button.disabled = true; button.textContent = 'Mengirim…';
  try {
    const data = await request('/api/send', {method: 'POST'});
    notify(data.output || 'Pengiriman selesai.');
  } catch (error) { notify(error.message, true); }
  finally { button.disabled = false; button.textContent = 'Kirim sekarang'; }
};

document.querySelector('#cookieFile').onchange = async event => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    const parsed = JSON.parse(await file.text());
    const data = await request('/api/cookies', {method: 'POST', body: JSON.stringify({cookies: parsed})});
    document.querySelector('#cookieStatus').textContent = 'Cookie TikTok siap';
    document.querySelector('#statusDot').classList.add('ready');
    notify(`${data.saved} cookie valid tersimpan.`);
  } catch (error) { notify(`Cookie gagal: ${error.message}`, true); }
  event.target.value = '';
};

load();
