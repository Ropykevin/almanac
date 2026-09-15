(() => {
  const root = document.querySelector("[data-public-nav]");
  if (root) {
    const toggle = root.querySelector("[data-nav-toggle]");
    const panel = root.querySelector("[data-mobile-nav]");
    if (toggle && panel) {
      const setOpen = (open) => {
        panel.classList.toggle("hidden", !open);
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
      };

      toggle.addEventListener("click", () => {
        const open = toggle.getAttribute("aria-expanded") !== "true";
        setOpen(open);
      });

      window.addEventListener("resize", () => {
        if (window.matchMedia("(min-width: 768px)").matches) setOpen(false);
      });
    }
  }

  // Legacy: if any reveal-on-scroll nodes remain, force them visible immediately.
  document.querySelectorAll(".reveal-on-scroll").forEach((el) => {
    el.classList.add("is-visible");
    el.style.opacity = "1";
    el.style.transform = "none";
    el.style.visibility = "visible";
  });

  // Reading progress on article pages
  const progress = document.querySelector("[data-reading-progress]");
  const articleBody = document.querySelector("[data-article-body]");
  if (progress && articleBody) {
    const onScroll = () => {
      const rect = articleBody.getBoundingClientRect();
      const total = articleBody.offsetHeight - window.innerHeight;
      const scrolled = Math.min(Math.max(-rect.top, 0), Math.max(total, 1));
      const pct = total > 0 ? (scrolled / total) * 100 : 0;
      progress.style.width = `${pct}%`;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  // Like + share on article pages
  const engage = document.querySelector("[data-article-engage]");
  if (engage) {
    const likeBtn = engage.querySelector("[data-like-btn]");
    const likeCount = engage.querySelector("[data-like-count]");
    const likeLabel = engage.querySelector("[data-like-label]");
    const likeUrl = engage.dataset.likeUrl;
    const csrfToken = engage.dataset.csrfToken;

    if (likeBtn && likeUrl) {
      likeBtn.addEventListener("click", async () => {
        likeBtn.disabled = true;
        try {
          const res = await fetch(likeUrl, {
            method: "POST",
            headers: {
              "X-Requested-With": "XMLHttpRequest",
              "X-CSRFToken": csrfToken || "",
              Accept: "application/json",
            },
            credentials: "same-origin",
          });
          const data = await res.json();
          if (!res.ok || !data.ok) throw new Error(data.error || "Like failed");
          likeBtn.classList.toggle("is-active", !!data.liked);
          likeBtn.setAttribute("aria-pressed", data.liked ? "true" : "false");
          if (likeLabel) likeLabel.textContent = data.liked ? "Liked" : "Like";
          if (likeCount) likeCount.textContent = String(data.count ?? 0);
          const icon = likeBtn.querySelector("svg");
          if (icon) icon.setAttribute("fill", data.liked ? "currentColor" : "none");
        } catch (_) {
          // Fall back to full form post if fetch fails
          const form = document.createElement("form");
          form.method = "POST";
          form.action = likeUrl;
          const token = document.createElement("input");
          token.type = "hidden";
          token.name = "csrf_token";
          token.value = csrfToken || "";
          form.appendChild(token);
          document.body.appendChild(form);
          form.submit();
        } finally {
          likeBtn.disabled = false;
        }
      });
    }

    const shareMenu = engage.querySelector("[data-share-menu]");
    const shareToggle = engage.querySelector("[data-share-toggle]");
    const sharePanel = engage.querySelector("[data-share-panel]");
    const copyBtn = engage.querySelector("[data-copy-link]");
    const nativeShare = engage.querySelector("[data-native-share]");
    const shareUrl = engage.dataset.shareUrl || window.location.href;
    const shareTitle = engage.dataset.shareTitle || document.title;

    if (shareToggle && sharePanel) {
      const setOpen = (open) => {
        sharePanel.classList.toggle("hidden", !open);
        shareToggle.setAttribute("aria-expanded", open ? "true" : "false");
      };
      shareToggle.addEventListener("click", () => {
        setOpen(shareToggle.getAttribute("aria-expanded") !== "true");
      });
      document.addEventListener("click", (event) => {
        if (shareMenu && !shareMenu.contains(event.target)) setOpen(false);
      });
    }

    if (copyBtn) {
      const copyLabel = copyBtn.querySelector("[data-copy-label]");
      copyBtn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(shareUrl);
          if (copyLabel) {
            copyLabel.textContent = "Copied";
            setTimeout(() => {
              copyLabel.textContent = "Copy link";
            }, 1600);
          }
        } catch (_) {
          window.prompt("Copy this link:", shareUrl);
        }
      });
    }

    if (nativeShare && navigator.share) {
      nativeShare.classList.remove("hidden");
      nativeShare.addEventListener("click", async () => {
        try {
          await navigator.share({ title: shareTitle, url: shareUrl });
        } catch (_) {
          /* user cancelled */
        }
      });
    }
  }
})();
