(() => {
  const root = document.querySelector("[data-article-form]");
  if (!root) return;

  const titleInput = document.getElementById("article-title");
  const slugInput = document.getElementById("article-slug");
  const statusSelect = document.getElementById("article-status");
  const scheduleField = document.getElementById("schedule-field");
  const contentField = document.getElementById("article-content");
  const form = root.querySelector("form");
  const uploadUrl = root.dataset.uploadUrl;
  const mediaPickerUrl = root.dataset.mediaPickerUrl;
  const csrfToken = root.dataset.csrfToken;

  const openMediaPicker = (kind = "image") =>
    new Promise((resolve, reject) => {
      if (!mediaPickerUrl) {
        reject(new Error("Media picker is not configured."));
        return;
      }
      const separator = mediaPickerUrl.includes("?") ? "&" : "?";
      const win = window.open(
        `${mediaPickerUrl}${separator}kind=${encodeURIComponent(kind)}`,
        "LiminalMediaPicker",
        "width=960,height=720,menubar=no,toolbar=no"
      );
      if (!win) {
        reject(new Error("Pop-up blocked. Allow pop-ups to open the media library."));
        return;
      }
      const onMessage = (event) => {
        if (event.origin !== window.location.origin) return;
        if (!event.data || !event.data.liminalMedia || !event.data.url) return;
        window.removeEventListener("message", onMessage);
        resolve(event.data);
      };
      window.addEventListener("message", onMessage);
      const timer = window.setInterval(() => {
        if (win.closed) {
          window.clearInterval(timer);
          window.removeEventListener("message", onMessage);
          reject(new Error("Media picker closed."));
        }
      }, 400);
    });

  const slugify = (value) =>
    value
      .toString()
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim()
      .replace(/[^\w\s-]/g, "")
      .replace(/[\s_-]+/g, "-")
      .replace(/^-+|-+$/g, "");

  let slugTouched = Boolean(slugInput && slugInput.value.trim());

  if (slugInput) {
    slugInput.addEventListener("input", () => {
      slugTouched = slugInput.value.trim().length > 0;
    });
  }

  if (titleInput && slugInput) {
    titleInput.addEventListener("input", () => {
      if (slugTouched) return;
      slugInput.value = slugify(titleInput.value);
    });
  }

  const syncScheduleVisibility = () => {
    if (!statusSelect || !scheduleField) return;
    const scheduled = statusSelect.value === "SCHEDULED";
    scheduleField.classList.toggle("hidden", !scheduled);
  };

  if (statusSelect) {
    statusSelect.addEventListener("change", syncScheduleVisibility);
    syncScheduleVisibility();
  }

  const ensureFootnotesAside = (editor) => {
    const body = editor.getBody();
    let aside = body.querySelector("aside.footnotes");
    if (!aside) {
      aside = editor.getDoc().createElement("aside");
      aside.className = "footnotes";
      aside.setAttribute("role", "doc-endnotes");
      aside.innerHTML = "<h2>Footnotes</h2><ol></ol>";
      body.appendChild(aside);
    }
    let list = aside.querySelector("ol");
    if (!list) {
      list = editor.getDoc().createElement("ol");
      aside.appendChild(list);
    }
    return list;
  };

  const registerFootnoteButton = (editor) => {
    editor.ui.registry.addButton("footnote", {
      text: "Footnote",
      tooltip: "Insert footnote",
      onAction: () => {
        editor.windowManager.open({
          title: "Insert footnote",
          body: {
            type: "panel",
            items: [
              {
                type: "input",
                name: "text",
                label: "Footnote text",
              },
            ],
          },
          buttons: [
            { type: "cancel", text: "Cancel" },
            { type: "submit", text: "Insert", primary: true },
          ],
          onSubmit: (api) => {
            const text = (api.getData().text || "").trim();
            if (!text) {
              api.close();
              return;
            }
            const list = ensureFootnotesAside(editor);
            const index = list.children.length + 1;
            const fnId = `fn-${Date.now()}-${index}`;
            const refId = `${fnId}-ref`;

            editor.insertContent(
              `<sup class="footnote-ref" id="${refId}">` +
                `<a href="#${fnId}" role="doc-noteref">${index}</a></sup>`
            );

            const li = editor.getDoc().createElement("li");
            li.id = fnId;
            li.setAttribute("role", "doc-endnote");
            li.innerHTML =
              `${editor.dom.encode(text)} ` +
              `<a href="#${refId}" role="doc-backlink" aria-label="Back to content">↩</a>`;
            list.appendChild(li);
            api.close();
          },
        });
      },
    });
  };

  const initEditor = () => {
    if (!contentField || typeof tinymce === "undefined") return;

    tinymce.init({
      target: contentField,
      license_key: "gpl",
      menubar: "edit view insert format table tools",
      branding: false,
      promotion: false,
      height: 520,
      resize: true,
      convert_urls: false,
      relative_urls: false,
      remove_script_host: false,
      browser_spellcheck: true,
      paste_data_images: true,
      automatic_uploads: true,
      images_reuse_filename: false,
      image_caption: true,
      image_advtab: true,
      image_title: true,
      object_resizing: true,
      table_use_colgroups: true,
      table_default_attributes: { border: "0" },
      table_default_styles: { width: "100%" },
      codesample_languages: [
        { text: "HTML/XML", value: "markup" },
        { text: "JavaScript", value: "javascript" },
        { text: "CSS", value: "css" },
        { text: "Python", value: "python" },
        { text: "JSON", value: "json" },
        { text: "Bash", value: "bash" },
      ],
      block_formats:
        "Paragraph=p; Heading 2=h2; Heading 3=h3; Heading 4=h4; Heading 5=h5; Heading 6=h6",
      plugins:
        "advlist autolink lists link image media table codesample code " +
        "charmap fullscreen wordcount autoresize visualblocks",
      toolbar:
        "undo redo | blocks | bold italic underline superscript | " +
        "alignleft aligncenter alignright | bullist numlist blockquote | " +
        "link image medialibrary media table codesample footnote | removeformat | code fullscreen",
      content_style: `
        body {
          font-family: "DM Sans", system-ui, sans-serif;
          font-size: 16px;
          line-height: 1.7;
          color: #1c1917;
          max-width: 42rem;
          margin: 1rem auto;
          padding: 0 1rem;
        }
        h2, h3, h4, h5, h6 { font-family: "Source Serif 4", Georgia, serif; line-height: 1.25; }
        blockquote {
          border-left: 3px solid #0f766e;
          margin: 1.25rem 0;
          padding: 0.25rem 0 0.25rem 1rem;
          color: #44403c;
        }
        pre, code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
        pre { background: #f5f5f4; padding: 1rem; border-radius: 0.5rem; overflow: auto; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #e7e5e4; padding: 0.5rem 0.75rem; }
        th { background: #fafaf9; }
        figure { margin: 1.5rem 0; }
        figcaption { color: #78716c; font-size: 0.9rem; margin-top: 0.4rem; }
        iframe, video { max-width: 100%; }
        aside.footnotes {
          margin-top: 2.5rem;
          padding-top: 1rem;
          border-top: 1px solid #e7e5e4;
          font-size: 0.92rem;
          color: #57534e;
        }
        .footnote-ref a { text-decoration: none; }
      `,
      setup: (editor) => {
        registerFootnoteButton(editor);
        editor.ui.registry.addButton("medialibrary", {
          text: "Media library",
          tooltip: "Insert from media library",
          onAction: async () => {
            try {
              const selected = await openMediaPicker("image");
              if (selected.kind === "image") {
                editor.insertContent(
                  `<img src="${editor.dom.encode(selected.url)}" alt="${editor.dom.encode(
                    selected.alt || ""
                  )}" />`
                );
              } else {
                const label = editor.dom.encode(selected.name || selected.url);
                editor.insertContent(
                  `<a href="${editor.dom.encode(selected.url)}" target="_blank" rel="noopener">${label}</a>`
                );
              }
            } catch (_err) {
              /* user closed picker */
            }
          },
        });
      },
      file_picker_callback: (callback, _value, meta) => {
        const kind =
          meta.filetype === "media"
            ? "all"
            : meta.filetype === "file"
              ? "document"
              : "image";
        openMediaPicker(kind)
          .then((selected) => {
            if (meta.filetype === "image" && selected.kind !== "image") {
              callback(selected.url, { text: selected.name || selected.alt || "" });
              return;
            }
            callback(selected.url, {
              alt: selected.alt || "",
              text: selected.name || selected.alt || "",
              title: selected.name || "",
            });
          })
          .catch(() => {});
      },
      images_upload_handler: async (blobInfo) => {
        if (!uploadUrl) {
          throw new Error("Upload URL is not configured.");
        }
        const formData = new FormData();
        formData.append("file", blobInfo.blob(), blobInfo.filename());

        const response = await fetch(uploadUrl, {
          method: "POST",
          headers: csrfToken ? { "X-CSRFToken": csrfToken } : {},
          body: formData,
          credentials: "same-origin",
        });

        let payload = {};
        try {
          payload = await response.json();
        } catch (_err) {
          throw new Error("Invalid upload response.");
        }

        if (!response.ok || !payload.location) {
          throw new Error(payload.error || "Image upload failed.");
        }
        return payload.location;
      },
      file_picker_types: "image media",
      media_live_embeds: true,
      media_url_resolver: (data, resolve) => {
        const url = data.url || "";
        const yt =
          url.match(
            /(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu\.be\/)([A-Za-z0-9_-]{6,})/
          ) || [];
        const vimeo = url.match(/vimeo\.com\/(\d+)/) || [];
        if (yt[1]) {
          resolve({
            html:
              `<iframe src="https://www.youtube-nocookie.com/embed/${yt[1]}" ` +
              `width="560" height="315" allowfullscreen loading="lazy" ` +
              `referrerpolicy="strict-origin-when-cross-origin" title="YouTube video"></iframe>`,
          });
          return;
        }
        if (vimeo[1]) {
          resolve({
            html:
              `<iframe src="https://player.vimeo.com/video/${vimeo[1]}" ` +
              `width="560" height="315" allowfullscreen loading="lazy" ` +
              `referrerpolicy="strict-origin-when-cross-origin" title="Vimeo video"></iframe>`,
          });
          return;
        }
        resolve({ html: "" });
      },
    });
  };

  if (form) {
    form.addEventListener("submit", () => {
      if (typeof tinymce !== "undefined") {
        tinymce.triggerSave();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initEditor);
  } else {
    initEditor();
  }
})();
