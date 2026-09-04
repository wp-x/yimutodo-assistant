// ==UserScript==
// @name         一木清单 Cookie 一键提取
// @namespace    yimutodo
// @version      1.2
// @description  克隆原生 user-search 按钮结构，在搜索图标左边无缝插入同款"复制"图标按钮，一键提取 vertx-web.session(HttpOnly 也能读)到剪贴板
// @match        https://yimutodo.com/*
// @match        https://www.yimutodo.com/*
// @grant        GM_cookie
// @grant        GM_setClipboard
// @grant        GM_addStyle
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  const BTN_ID = 'yimu-cookie-btn';

  // 反馈颜色 + 与右侧 Search 按钮拉开间距(它 hover 会放大)
  GM_addStyle(`
    #${BTN_ID}{ margin-right: 10px !important; }
    #${BTN_ID}.ok svg{ color:#67c23a !important; }
    #${BTN_ID}.bad svg{ color:#f56c6c !important; }
  `);

  function insertButton() {
    if (document.getElementById(BTN_ID)) return;
    const anchor = document.querySelector('.user-search, div.user-search.hand, div.user-search');
    if (!anchor) { setTimeout(insertButton, 800); return; }

    // 克隆原生按钮结构(class/data-v 全保留 → 站点 CSS 100% 命中)
    const btn = anchor.cloneNode(false);
    btn.id = BTN_ID;
    btn.title = '复制Cookie';
    btn.innerHTML =
      '<svg data-v-972b9f6e="" class="svg-icon" aria-hidden="true" style="font-size: 16px;">' +
      '<use data-v-972b9f6e="" xlink:href="#icon-clipboard"></use></svg>';

    anchor.before(btn);
    btn.addEventListener('click', onExtract);
  }

  function onExtract() {
    GM_cookie.list({ name: 'vertx-web.session' }, (cookies, error) => {
      const btn = document.getElementById(BTN_ID);
      if (error || !cookies) { flash(btn, false); return; }
      const c = (cookies || []).find(x => x.name === 'vertx-web.session');
      if (!c || !c.value) { flash(btn, false); return; }
      GM_setClipboard('vertx-web.session=' + c.value, 'text');
      flash(btn, true);
    });
  }

  function flash(btn, ok) {
    if (!btn) return;
    btn.classList.add(ok ? 'ok' : 'bad');
    setTimeout(() => btn.classList.remove('ok', 'bad'), 1200);
  }

  // 启动: 页面加载完插入 + SPA 路由变化后保持存在
  function boot() {
    insertButton();
    new MutationObserver(() => insertButton()).observe(document.body, { childList: true, subtree: true });
    setTimeout(insertButton, 2000);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
