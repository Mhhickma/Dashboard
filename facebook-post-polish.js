// Clean up title fragments left behind after model-number removal.
(function () {
  function polishedText(value) {
    return String(value || "")
      .replace(/\b([A-Za-z]+)\s+x\s+(?=[A-Za-z]+\b)/g, "$1 ")
      .replace(/\s{2,}/g, " ")
      .trim();
  }

  function processBox(box) {
    if (box.dataset.polished === "true") return;
    var preview = box.querySelector(".facebook-post-preview");
    var oldButton = box.querySelector(".copy-facebook-post");
    var heading = box.querySelector(".facebook-post-heading");
    if (!preview || !oldButton) return;

    var text = polishedText(preview.textContent);
    preview.textContent = text;
    if (heading) heading.textContent = "Facebook Post - " + text.length + " characters";

    var button = oldButton.cloneNode(true);
    button.addEventListener("click", async function () {
      try {
        await navigator.clipboard.writeText(text);
        button.textContent = "Copied Facebook Post";
      } catch (error) {
        window.prompt("Copy this Facebook post:", text);
        button.textContent = "Post Ready";
      }
      window.setTimeout(function () { button.textContent = "Copy Facebook Post"; }, 1800);
    });
    oldButton.replaceWith(button);
    box.dataset.polished = "true";
  }

  function processPosts() {
    document.querySelectorAll(".facebook-post-box").forEach(processBox);
  }

  new MutationObserver(processPosts).observe(document.body, { childList: true, subtree: true });
  processPosts();
}());
