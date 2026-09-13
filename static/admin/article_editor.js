/* 記事本文エディタの画像挿入ツールバー（管理画面・記事編集ページ専用）
 *
 * WordPress のように「アップロードしながら本文の途中に画像を挿入」できるようにする。
 *   - ツールバーの「画像を挿入」ボタン（ファイル選択）
 *   - 本文エリアへのドラッグ&ドロップ
 *   - クリップボードからの貼り付け（スクリーンショット等）
 *   - アップロード済み画像のライブラリから再挿入
 * いずれもカーソル位置に <figure class="bk-mc-illust-figure"> を差し込む。
 *
 * 外部ライブラリなし（CDN不可）。textarea をそのまま使うので、既存のHTML直書き運用と共存する。
 */
(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function csrfToken() {
    const m = document.cookie.match(/(^|;)\s*csrftoken=([^;]+)/);
    if (m) return decodeURIComponent(m[2]);
    const el = document.querySelector("[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  // 記事IDを取得（変更ページのURL: /admin/products/article/<id>/change/）
  function articleId() {
    const m = window.location.pathname.match(/\/products\/article\/(\d+)\/change\//);
    return m ? m[1] : null;
  }

  function insertAtCursor(ta, text) {
    const start = ta.selectionStart || 0;
    const end = ta.selectionEnd || 0;
    const before = ta.value.slice(0, start);
    const after = ta.value.slice(end);
    // 前後に空行を確保して、HTMLブロックとして読みやすくする
    const pre = before && !before.endsWith("\n\n") ? (before.endsWith("\n") ? "\n" : "\n\n") : "";
    const post = after && !after.startsWith("\n\n") ? (after.startsWith("\n") ? "\n" : "\n\n") : "\n";
    const chunk = pre + text + post;
    ta.value = before + chunk + after;
    const pos = (before + chunk).length;
    ta.selectionStart = ta.selectionEnd = pos;
    ta.focus();
    ta.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function buildUI(ta, id) {
    const bar = document.createElement("div");
    bar.className = "ae-bar";
    bar.innerHTML =
      '<button type="button" class="ae-btn ae-upload">🖼 画像をアップロードして挿入</button>' +
      '<button type="button" class="ae-btn ae-library">📁 アップロード済みから挿入</button>' +
      '<span class="ae-hint">本文エリアに画像をドラッグ&ドロップ／スクリーンショットを貼り付け（Ctrl+V）でも挿入できます</span>' +
      '<span class="ae-status" aria-live="polite"></span>' +
      '<input type="file" class="ae-file" accept="image/*" multiple hidden>';
    ta.parentNode.insertBefore(bar, ta);

    const panel = document.createElement("div");
    panel.className = "ae-library-panel";
    panel.hidden = true;
    ta.parentNode.insertBefore(panel, ta.nextSibling);

    const status = bar.querySelector(".ae-status");
    const fileInput = bar.querySelector(".ae-file");

    function setStatus(msg, kind) {
      status.textContent = msg || "";
      status.className = "ae-status" + (kind ? " ae-" + kind : "");
      if (msg && kind === "ok") setTimeout(() => { status.textContent = ""; }, 4000);
    }

    async function upload(file) {
      if (!id) {
        setStatus("先に記事を保存してください（新規記事は保存後に画像を挿入できます）", "err");
        return null;
      }
      const fd = new FormData();
      fd.append("image", file);
      // alt はあとから「アップロード済みから挿入」パネルで編集できる
      fd.append("alt_text", "");
      setStatus("アップロード中… " + file.name);
      try {
        const res = await fetch(`/admin/products/article/${id}/upload-image/`, {
          method: "POST",
          headers: { "X-CSRFToken": csrfToken() },
          body: fd,
          credentials: "same-origin",
        });
        const data = await res.json();
        if (!res.ok) {
          setStatus("失敗: " + (data.error || res.status), "err");
          return null;
        }
        return data;
      } catch (e) {
        setStatus("通信に失敗しました: " + e, "err");
        return null;
      }
    }

    async function uploadAndInsert(files) {
      for (const f of files) {
        if (!f.type.startsWith("image/")) continue;
        const data = await upload(f);
        if (data) {
          insertAtCursor(ta, data.html);
          setStatus("挿入しました（alt・キャプションは「アップロード済みから挿入」で編集できます）", "ok");
        }
      }
    }

    bar.querySelector(".ae-upload").addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", () => {
      uploadAndInsert(Array.from(fileInput.files || []));
      fileInput.value = "";
    });

    // ドラッグ&ドロップ
    ["dragenter", "dragover"].forEach((ev) =>
      ta.addEventListener(ev, (e) => {
        if (e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files")) {
          e.preventDefault();
          ta.classList.add("ae-dragover");
        }
      })
    );
    ["dragleave", "drop"].forEach((ev) =>
      ta.addEventListener(ev, () => ta.classList.remove("ae-dragover"))
    );
    ta.addEventListener("drop", (e) => {
      const files = e.dataTransfer && e.dataTransfer.files;
      if (files && files.length) {
        e.preventDefault();
        uploadAndInsert(Array.from(files));
      }
    });

    // クリップボード貼り付け（スクリーンショット）
    ta.addEventListener("paste", (e) => {
      const items = (e.clipboardData && e.clipboardData.items) || [];
      const imgs = [];
      for (const it of items) {
        if (it.kind === "file" && it.type.startsWith("image/")) {
          const f = it.getAsFile();
          if (f) imgs.push(f);
        }
      }
      if (imgs.length) {
        e.preventDefault();
        uploadAndInsert(imgs);
      }
    });

    // ライブラリ（アップロード済み画像）
    async function renderLibrary() {
      if (!id) {
        panel.innerHTML = '<p class="ae-empty">記事を保存すると、アップロード済み画像がここに並びます。</p>';
        return;
      }
      panel.innerHTML = '<p class="ae-empty">読み込み中…</p>';
      const res = await fetch(`/admin/products/article/${id}/images/`, { credentials: "same-origin" });
      const data = await res.json();
      const imgs = data.images || [];
      if (!imgs.length) {
        panel.innerHTML = '<p class="ae-empty">この記事にはまだ画像がありません。上のボタンかドラッグ&ドロップでアップロードしてください。</p>';
        return;
      }
      panel.innerHTML = "";
      imgs.forEach((im) => {
        const card = document.createElement("div");
        card.className = "ae-card";
        card.innerHTML =
          `<img src="${im.url}" alt="">` +
          `<input type="text" class="ae-alt" placeholder="alt（画像の説明）" value="${(im.alt || "").replace(/"/g, "&quot;")}">` +
          `<input type="text" class="ae-cap" placeholder="キャプション（任意）" value="${(im.caption || "").replace(/"/g, "&quot;")}">` +
          `<button type="button" class="ae-btn ae-insert">この位置に挿入</button>`;
        card.querySelector(".ae-insert").addEventListener("click", async () => {
          const alt = card.querySelector(".ae-alt").value.trim();
          const cap = card.querySelector(".ae-cap").value.trim();
          // alt/キャプションの変更を保存してから、確定したHTMLを挿入する
          const res2 = await fetch(`/admin/products/article-image/${im.id}/update/`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
            body: JSON.stringify({ alt_text: alt, caption: cap }),
            credentials: "same-origin",
          });
          const d2 = await res2.json();
          insertAtCursor(ta, d2.html || im.html);
          setStatus("挿入しました", "ok");
        });
        panel.appendChild(card);
      });
    }

    bar.querySelector(".ae-library").addEventListener("click", () => {
      panel.hidden = !panel.hidden;
      if (!panel.hidden) renderLibrary();
    });
  }

  ready(function () {
    const ta = document.querySelector("textarea[data-article-editor]");
    if (!ta) return;
    buildUI(ta, articleId());
  });
})();
