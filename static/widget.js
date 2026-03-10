(function () {
  if (window.__ashWidget) return;
  window.__ashWidget = true;

  var BASE = '';
  try {
    var scripts = document.querySelectorAll('script[src]');
    for (var i = 0; i < scripts.length; i++) {
      if (scripts[i].src.indexOf('widget.js') !== -1) {
        BASE = new URL(scripts[i].src).origin;
        break;
      }
    }
  } catch (e) {}

  var style = document.createElement('style');
  style.textContent = [
    '#ash-wb{position:fixed;bottom:24px;right:24px;',
    'width:60px;height:60px;border-radius:50%;',
    'background:#e8650a;box-shadow:0 4px 20px rgba(232,101,10,0.55);',
    'cursor:pointer;z-index:2147483646;display:flex;align-items:center;',
    'justify-content:center;border:none;transition:transform .2s,box-shadow .2s;padding:0;}',
    '#ash-wb:hover{transform:scale(1.08);box-shadow:0 6px 28px rgba(232,101,10,0.75);}',
    '#ash-wb svg{width:28px;height:28px;}',
    '#ash-tooltip{position:fixed;bottom:92px;right:24px;',
    'background:#1a1a1a;color:#f0f0f0;font-family:Inter,sans-serif;',
    'font-size:13px;font-weight:500;padding:8px 14px;border-radius:8px;',
    'box-shadow:0 4px 20px rgba(0,0,0,0.4);border:1px solid rgba(255,255,255,0.1);',
    'white-space:nowrap;z-index:2147483645;',
    'opacity:0;transform:translateY(6px);pointer-events:none;',
    'transition:opacity .2s,transform .2s;}',
    '#ash-wb:hover + #ash-tooltip{opacity:1;transform:translateY(0);}',
  ].join('');
  document.head.appendChild(style);

  var btn = document.createElement('button');
  btn.id = 'ash-wb';
  btn.title = 'Chat with Ash — Pacific Construction';
  btn.setAttribute('aria-label', 'Chat with Pacific Construction');
  btn.innerHTML = '<svg viewBox="0 0 24 24" fill="white"><path d="M20 2H4a2 2 0 00-2 2v18l4-4h14a2 2 0 002-2V4a2 2 0 00-2-2z"/></svg>';
  btn.addEventListener('click', function () {
    window.open(BASE + '/', '_blank', 'noopener');
  });
  document.body.appendChild(btn);

  var tooltip = document.createElement('div');
  tooltip.id = 'ash-tooltip';
  tooltip.textContent = 'Chat with Ash';
  document.body.appendChild(tooltip);
})();
