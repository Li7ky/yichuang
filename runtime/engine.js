/*
 * 译窗 — Cursor 中文界面运行时
 * Generated: __BUILD_TIMESTAMP__
 */
(function () {
  'use strict';
  if (window.__YICHUANG_CN__) return;
  window.__YICHUANG_CN__ = true;

  // __DICTIONARY_BLOCK__
  // __PATTERN_BLOCK__
  // __FRAGMENT_BLOCK__

  var SKIP_TAGS = {
    TEXTAREA: 1, INPUT: 1, SCRIPT: 1, STYLE: 1, CODE: 1, PRE: 1,
    NOSCRIPT: 1, SVG: 1, MATH: 1, KBD: 1
  };

  // 跳过编辑器正文 / 对话流内容 / 文件树文件名等，避免无意义扫描与误翻
  var SKIP_CLOSEST =
    '.monaco-editor .view-lines,' +
    '.monaco-editor .view-line,' +
    '.overflow-guard,' +
    '.inputarea,' +
    '.native-edit-context,' +
    '[contenteditable="true"],' +
    '.composer-message-content,' +
    '.markdown-body,' +
    '.anysphere-markdown-container,' +
    '.chat-message,' +
    '.aislash-editor-input,' +
    '.explorer-folders-view .monaco-tl-row,' +
    '.monaco-list-row .label-name,' +
    '.terminal-wrapper,' +
    '.xterm,' +
    '.debug-hover-widget';

  // 记录节点上次处理时的原文；内容变化才再翻，避免漏翻又避免重复劳动
  var lastSeen = typeof WeakMap !== 'undefined' ? new WeakMap() : null;
  var pending = [];
  var pendingSet = typeof WeakSet !== 'undefined' ? new WeakSet() : null;
  var flushTimer = 0;
  var lastFullScan = 0;
  var translating = false;
  var marketLoaded = false;

  function norm(s) {
    return s.replace(/\s+/g, ' ').trim();
  }

  function quoteNorm(s) {
    return s
      .replace(/[\u2018\u2019\u2032]/g, "'")
      .replace(/[\u201C\u201D\u2033]/g, '"');
  }

  function shouldSkipEl(el) {
    if (!el || el.nodeType !== 1) return true;
    if (SKIP_TAGS[el.tagName]) return true;
    try {
      if (el.closest && el.closest(SKIP_CLOSEST)) return true;
    } catch (e) {}
    return false;
  }

  function lookup(text) {
    if (!text || text.length > 400) return null;
    var t = text.trim();
    if (!t || t.length < 2) return null;
    if (/^[\d\s\.\,\:\;\-\+\=\/\*\(\)\[\]\{\}\|<>@#$%^&!~`'"\\]+$/.test(t)) return null;
    if (/^[a-z][\w-]*(?:\.[A-Za-z][\w-]*){1,}$/.test(t)) return null;
    if (/^[\\\/]?[\w.-]+(?:[\\\/][\w.-]+)+$/.test(t)) return null;

    var n = norm(text);
    var q = quoteNorm(n);

    if (DICT.has(t)) return DICT.get(t);
    if (n !== t && DICT.has(n)) return DICT.get(n);
    if (q !== n && DICT.has(q)) return DICT.get(q);

    // 含中文的已译文案直接跳过；过长正则扫描也跳过
    if (/[\u4e00-\u9fff]/.test(t)) return null;
    if (t.length <= 120 && PATTERNS.length) {
      for (var i = 0; i < PATTERNS.length; i++) {
        var p = PATTERNS[i];
        if (p[0].test(t)) return t.replace(p[0], p[1]);
      }
    }

    if (FRAGMENTS.length && t.length > 12 && t.length <= 320) {
      var result = q;
      var changed = false;
      for (var j = 0; j < FRAGMENTS.length; j++) {
        var from = FRAGMENTS[j][0];
        if (result.indexOf(from) !== -1) {
          result = result.split(from).join(FRAGMENTS[j][1]);
          changed = true;
        }
      }
      if (changed) return result;
    }

    return null;
  }

  function applyTextNode(node) {
    if (!node || node.nodeType !== 3) return;
    var parent = node.parentElement;
    if (!parent || shouldSkipEl(parent)) return;
    var raw = node.nodeValue;
    if (!raw || !raw.trim()) return;
    if (lastSeen && lastSeen.get(node) === raw) return;
    var tr = lookup(raw);
    if (tr && tr !== raw) {
      node.nodeValue = raw.replace(raw.trim(), tr);
    }
    if (lastSeen) lastSeen.set(node, node.nodeValue);
  }

  function applyAttr(el, attr) {
    if (!el || !el.getAttribute) return;
    var v = el.getAttribute(attr);
    if (!v || !v.trim()) return;
    var tr = lookup(v);
    if (tr && tr !== v) el.setAttribute(attr, tr);
  }

  function walk(root, budget) {
    if (!root) return;
    if (root.nodeType === 3) {
      applyTextNode(root);
      return;
    }
    if (root.nodeType !== 1) return;
    if (shouldSkipEl(root)) return;

    applyAttr(root, 'title');
    applyAttr(root, 'aria-label');
    applyAttr(root, 'placeholder');

    var doc = root.ownerDocument || document;
    var walker;
    try {
      walker = doc.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    } catch (e) {
      return;
    }
    var n;
    var count = 0;
    var limit = budget || 800;
    while ((n = walker.nextNode())) {
      applyTextNode(n);
      if (++count >= limit) break;
    }
  }

  function enqueue(node) {
    if (!node) return;
    if (pendingSet) {
      if (pendingSet.has(node)) return;
      pendingSet.add(node);
    }
    pending.push(node);
    if (!flushTimer) {
      flushTimer = setTimeout(flush, 180);
    }
  }

  function flush() {
    flushTimer = 0;
    if (translating) {
      flushTimer = setTimeout(flush, 120);
      return;
    }
    translating = true;
    var batch = pending;
    pending = [];
    pendingSet = typeof WeakSet !== 'undefined' ? new WeakSet() : null;
    try {
      var i = 0;
      function step() {
        var start = Date.now();
        while (i < batch.length && Date.now() - start < 8) {
          walk(batch[i++], 400);
        }
        if (i < batch.length) {
          requestAnimationFrame(step);
        } else {
          translating = false;
        }
      }
      step();
    } catch (e) {
      translating = false;
    }
  }

  function fullScanLight() {
    var now = Date.now();
    if (now - lastFullScan < 4000) return;
    lastFullScan = now;
    // 只扫壳层 UI，避免 [class*=composer/agent] 这种宽匹配拖慢对话区
    var roots = document.querySelectorAll(
      '.part.titlebar,' +
      '.part.statusbar,' +
      '.part.sidebar .composite.title,' +
      '.part.auxiliarybar .composite.title,' +
      '.quick-input-widget,' +
      '.context-view,' +
      '.monaco-menu,' +
      '.notifications-toasts,' +
      '.ui-menu,' +
      '.ui-dialog,' +
      '[aria-label="Settings"],' +
      '.settings-editor,' +
      '.monaco-workbench .part.editor .tabs-container'
    );
    for (var i = 0; i < roots.length; i++) enqueue(roots[i]);
  }

  function onMutations(mutations) {
    // 增量：只处理新增节点，不再顺带全扫
    for (var i = 0; i < mutations.length; i++) {
      var m = mutations[i];
      if (m.type === 'childList') {
        for (var j = 0; j < m.addedNodes.length; j++) {
          var n = m.addedNodes[j];
          if (n.nodeType === 1 || n.nodeType === 3) enqueue(n);
        }
      }
    }
  }

  function maybeLoadMarket() {
    if (marketLoaded) return;
    try {
      var href = String(location.href || '');
      var title = String(document.title || '');
      if (/extension|marketplace|gallery/i.test(href + title) ||
          document.querySelector('.extensions-viewlet, .extensions-list, [class*="marketplace"]')) {
        marketLoaded = true;
        // __MARKET_BLOCK__
      }
    } catch (e) {}
  }

  function boot() {
    var target = document.documentElement || document.body;
    if (!target) {
      setTimeout(boot, 50);
      return;
    }

    try {
      if (window.__CURSOR_LOCALIZATION__ || document.getElementById('cursor-localization-market-toggle-wrap')) {
        console.warn('[译窗] 检测到旧版汉化仍在运行，请先「一键还原」再重新汉化。');
      }
    } catch (e) {}

    var obs = new MutationObserver(onMutations);
    obs.observe(target, { childList: true, subtree: true });

    setTimeout(function () {
      fullScanLight();
      maybeLoadMarket();
    }, 800);

    setTimeout(function () {
      fullScanLight();
      maybeLoadMarket();
    }, 2500);

    // 仅命令面板/菜单快捷键时补扫，不在每次点击时全扫
    document.addEventListener('keydown', function (e) {
      if (e.key === 'F1' || (e.ctrlKey && e.shiftKey && (e.key === 'P' || e.key === 'p')) || e.key === 'ContextMenu') {
        setTimeout(fullScanLight, 200);
      }
    }, true);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
