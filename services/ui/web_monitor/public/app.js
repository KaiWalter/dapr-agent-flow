(function(){
  const chat = document.getElementById('chat');
  const status = document.getElementById('status');
  const topicLabel = document.getElementById('topic');

  function escapeHtml(str){
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }

  // Minimal Markdown renderer (headings, bold, italic, code, lists)
  function renderMarkdown(text){
    if (!text) return '';
    let html = escapeHtml(String(text));

    // Code blocks ```
    html = html.replace(/```([\s\S]*?)```/g, (m, p1) => `<pre class="code"><code>${p1}</code></pre>`);
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    // Headings
    html = html.replace(/^######\s+(.+)$/gm, '<h6>$1</h6>')
               .replace(/^#####\s+(.+)$/gm, '<h5>$1</h5>')
               .replace(/^####\s+(.+)$/gm, '<h4>$1</h4>')
               .replace(/^###\s+(.+)$/gm, '<h3>$1</h3>')
               .replace(/^##\s+(.+)$/gm, '<h2>$1</h2>')
               .replace(/^#\s+(.+)$/gm, '<h1>$1</h1>');
    // Bold and italic
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
               .replace(/\*([^*]+)\*/g, '<em>$1</em>')
               .replace(/__([^_]+)__ /g, '<strong>$1</strong>')
               .replace(/_([^_]+)_/g, '<em>$1</em>');

    // Lists: group consecutive list items
    html = groupList(html, /^\s*[-*]\s+(.+)$/gm, 'ul');
    html = groupList(html, /^\s*\d+\.\s+(.+)$/gm, 'ol');

    // Paragraph breaks
    html = html.replace(/\n{2,}/g, '<br/><br/>' );
    html = html.replace(/\n/g, '<br/>' );
    return html;
  }

  function groupList(input, regex, tag){
    const lines = input.split('\n');
    const out = [];
    let inList = false;
    for (const line of lines){
      const m = line.match(regex);
      if (m){
        if (!inList){ out.push(`<${tag}>`); inList = true; }
        out.push(`<li>${line.replace(regex, '$1')}</li>`);
      } else {
        if (inList){ out.push(`</${tag}>`); inList = false; }
        out.push(line);
      }
    }
    if (inList) out.push(`</${tag}>`);
    return out.join('\n');
  }

  function resolveActor(source){
    const s = (source || '').toLowerCase();
    if (s.includes('orchestrator') || s.includes('intent')){
      return { emoji: '🧭', label: 'IntentOrchestrator' };
    }
    if (s.includes('task') || s.includes('planner')){
      return { emoji: '📝', label: 'TaskPlanner' };
    }
    if (s.includes('office') || s.includes('automation') || s.includes('emailer')){
      return { emoji: '🤖', label: 'OfficeAutomation' };
    }
    return { emoji: '💬', label: source || 'unknown' };
  }

  function sideFor(source){
    const s = (source || '').toLowerCase();
    return s.includes('agent') ? 'right' : 'left';
  }

  function render(msg){
    const { emoji, label } = resolveActor(msg.source);
    const wrapper = document.createElement('div');
    wrapper.className = `msg ${sideFor(msg.source)}`;

    const meta = document.createElement('div');
    meta.className = 'meta';
    const time = new Date(msg.time || Date.now()).toLocaleString();
    meta.innerHTML = `<span class="actor"><span class="icon">${emoji}</span>${label}</span> • ${time}`;

    const bubble = document.createElement('div');
    bubble.className = 'bubble';

    const content = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content, null, 2);
    bubble.innerHTML = renderMarkdown(content);

    wrapper.appendChild(meta);
    wrapper.appendChild(bubble);
    chat.appendChild(wrapper);
    chat.scrollTop = chat.scrollHeight;
  }

  function setStatus(text, ok){
    status.textContent = text;
    status.className = `status ${ok ? 'ok' : 'err'}`;
  }

  try {
    const es = new EventSource('/events');
    setStatus('Connected', true);

    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        render(data);
      } catch (e) {
        console.error('bad message', e);
      }
    };
    es.onerror = () => setStatus('Disconnected. Retrying…', false);
  } catch (e) {
    setStatus('SSE unsupported in this browser', false);
  }

  topicLabel.textContent = 'beacon_channel';
})();
