(function () {
  var MAX_LENGTH = 129;
  var POSTS_TO_SHOW = 4;
  var USED_KEY_PREFIX = "dashboard-used-engagement-posts-";
  var posts = [
    "What tool in your shop gets used way more than you expected?",
    "What is one woodworking tool you wish you had bought sooner?",
    "Shop question: do you prefer building with plans, sketches, or figuring it out as you go?",
    "What is your favorite small upgrade that made your shop easier to work in?",
    "What woodworking mistake taught you the most?",
    "If you could add one tool to your shop today, what would it be?",
    "What is your go-to finish for shop projects?",
    "What is the most underrated tool on your bench right now?",
    "Do you keep scrap wood, or do you force yourself to toss it?",
    "What is one clamp, jig, or accessory you reach for constantly?",
    "What project is currently sitting unfinished in your shop?",
    "What is your favorite way to keep sawdust under control?",
    "Table saw, miter saw, or router: which one do you use the most?",
    "What is one safety habit every new woodworker should learn early?",
    "What shop storage idea actually worked for you?",
    "What is a tool you bought cheap but still love?",
    "What is your favorite wood to work with and why?",
    "What is one shop tip you learned the hard way?",
    "Weekend shop check: are you building, organizing, sharpening, or cleaning today?",
    "What tool brand has treated you best over the years?"
  ];

  function dayKey(date) {
    return Math.floor(new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime() / 86400000);
  }

  function todayKey() {
    var now = new Date();
    return now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0") + "-" + String(now.getDate()).padStart(2, "0");
  }

  function usedKey() {
    return USED_KEY_PREFIX + todayKey();
  }

  function readUsedPosts() {
    try {
      return new Set(JSON.parse(localStorage.getItem(usedKey()) || "[]"));
    } catch (error) {
      return new Set();
    }
  }

  function writeUsedPosts(used) {
    localStorage.setItem(usedKey(), JSON.stringify(Array.from(used)));
  }

  function dailyPosts() {
    var start = dayKey(new Date()) % posts.length;
    var used = readUsedPosts();
    var ordered = [];

    for (var index = 0; index < posts.length; index += 1) {
      var text = posts[(start + index) % posts.length].slice(0, MAX_LENGTH);
      if (!used.has(text)) ordered.push(text);
      if (ordered.length === POSTS_TO_SHOW) break;
    }

    return ordered;
  }

  function markUsed(text) {
    var used = readUsedPosts();
    used.add(text);
    writeUsedPosts(used);
    render();
  }

  async function copyText(text, button) {
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = "Copied";
    } catch (error) {
      window.prompt("Copy this engagement post:", text);
      button.textContent = "Ready";
    }
    window.setTimeout(function () { button.textContent = "Copy"; }, 1600);
  }

  function render() {
    var list = document.getElementById("engagementPostList");
    if (!list) return;
    list.innerHTML = "";
    dailyPosts().forEach(function (text) {
      var item = document.createElement("article");
      item.className = "engagement-post-option";
      var copy = document.createElement("button");
      copy.type = "button";
      copy.textContent = "Copy";
      copy.addEventListener("click", function () { copyText(text, copy); });
      item.innerHTML = '<label class="engagement-used"><input type="checkbox"><span>Used</span></label><p></p><span>' + text.length + ' characters</span>';
      item.querySelector("p").textContent = text;
      item.querySelector("input").addEventListener("change", function () { markUsed(text); });
      item.appendChild(copy);
      list.appendChild(item);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", render);
  else render();
}());
