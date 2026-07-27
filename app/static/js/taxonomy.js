(() => {
  const nameInput = document.getElementById("taxonomy-name");
  const slugInput = document.getElementById("taxonomy-slug");
  if (!nameInput || !slugInput) return;

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

  let slugTouched = Boolean(slugInput.value.trim());
  slugInput.addEventListener("input", () => {
    slugTouched = slugInput.value.trim().length > 0;
  });
  nameInput.addEventListener("input", () => {
    if (slugTouched) return;
    slugInput.value = slugify(nameInput.value);
  });
})();
