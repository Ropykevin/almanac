(() => {
  const shell = document.querySelector("[data-admin-shell]");
  if (!shell) return;

  const sidebar = document.getElementById("admin-sidebar");
  const backdrop = document.getElementById("admin-sidebar-backdrop");
  const toggle = document.getElementById("admin-sidebar-toggle");
  if (!sidebar || !backdrop || !toggle) return;

  const setOpen = (open) => {
    sidebar.classList.toggle("-translate-x-full", !open);
    backdrop.classList.toggle("hidden", !open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
    document.body.classList.toggle("overflow-hidden", open);
  };

  toggle.addEventListener("click", () => {
    const open = toggle.getAttribute("aria-expanded") !== "true";
    setOpen(open);
  });

  backdrop.addEventListener("click", () => setOpen(false));

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setOpen(false);
  });

  window.addEventListener("resize", () => {
    if (window.matchMedia("(min-width: 1024px)").matches) setOpen(false);
  });
})();
