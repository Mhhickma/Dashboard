(function () {
  var MAX_LENGTH = 129;
  var POSTS_TO_SHOW = 4;
  var USED_KEY_PREFIX = "dashboard-used-engagement-posts-";
  var posts = [
    "What tool in your shop gets used way more than you expected?",
    "What\u2019s the best trick you\u2019ve learned for hiding a woodworking mistake?",
    "What\u2019s currently at the top of your woodworking wish list?",
    "What woodworking measurement gives beginners the most trouble?",
    "What woodworking opinion will you defend forever?",
    "Would you rather buy one premium tool or three budget tools?",
    "What species of wood do you hate working with?",
    "You can only keep FIVE tools from your shop. What are you keeping?",
    "What\u2019s the closest call you\u2019ve had in the shop?",
    "Brush, wipe, or spray your finishes?",
    "What project would you NEVER build again?",
    "Best tool under $100?",
    "What is your go-to finish for shop projects?",
    "What machine makes you the most nervous?",
    "What\u2019s your favorite saw?",
    "Do you sand between coats?",
    "What tool did you buy that you almost never use?",
    "What expensive tool actually lived up to the hype?",
    "Painted wood furniture\u2014acceptable or should wood stay natural?",
    "Is a full dust collection system worth the money?",
    "What woodworking purchase do you own way too many of?",
    "What finish do you find hardest to apply correctly?",
    "What homemade jig has saved you the most time?",
    "What woodworking technique took you the longest to learn?",
    "What\u2019s the best woodworking tool under $25?",
    "What\u2019s your favorite shop-storage solution?",
    "Random orbital sander or hand sanding?",
    "What was the first power tool you ever bought?",
    "What finishing mistake ruins a project fastest?",
    "What\u2019s your best \u201cI can fix that\u201d woodworking story?",
    "How many tape measures are currently hiding in your shop?",
    "Do you burn your scraps, save them, or throw them away?",
    "Do you keep scrap wood, or do you force yourself to toss it?",
    "What\u2019s the smallest project you\u2019ve ever made?",
    "Harbor Freight woodworking tools: what\u2019s worth buying?",
    "Weekend shop check: are you building, organizing, sharpening, or cleaning today?",
    "Digital measurements or old-school marks?",
    "How long does your shop stay clean after you clean it?",
    "Measure twice, cut once\u2026how many times do you actually measure?",
    "What\u2019s the most expensive mistake you\u2019ve made in the shop?",
    "When is a pocket hole the right answer?",
    "What\u2019s your favorite woodworking joint?",
    "What\u2019s the hardest part about pricing handmade woodworking?",
    "What wood smells the best when you cut it?",
    "Battery-powered table saws\u2014yes or no?",
    "What do you use for dust collection?",
    "Table saw or track saw\u2014if you could only keep one?",
    "What\u2019s the oldest tool you still regularly use?",
    "What woodworking tool could you absolutely not live without?",
    "What do you buy in bulk for your shop?",
    "What advice would you give yourself when you first started woodworking?",
    "What\u2019s your favorite hand tool?",
    "What is your favorite way to keep sawdust under control?",
    "Post a picture of your shop exactly how it looks RIGHT NOW.",
    "No cleaning first\u2014show us your workbench.",
    "What is your favorite small upgrade that made your shop easier to work in?",
    "New tools or used tools?",
    "Finish this sentence: \u201cYou know you\u2019re a woodworker when ______.\u201d",
    "Do you mark your waste side before cutting?",
    "What tool throws sawdust absolutely everywhere?",
    "What\u2019s the strangest piece of scrap wood you refuse to throw away?",
    "Glue or mechanical fasteners?",
    "What woodworking skill are you trying to improve right now?",
    "What cheap tool surprised you with how good it was?",
    "Parallel clamps or pipe clamps?",
    "Which tool brand do you think is overrated?",
    "What jig do you use the most?",
    "Furniture, cabinets, outdoor projects, or small crafts\u2014which do you enjoy most?",
    "What\u2019s your favorite wood finish?",
    "Coping saws\u2014underrated or outdated?",
    "What\u2019s the dustiest tool in your shop?",
    "Post your latest woodworking project\u2014finished or not.",
    "Do you organize your scrap wood or just throw it in a pile?",
    "What vintage woodworking tool would you love to own?",
    "Butt joints\u2014acceptable or woodworking crime?",
    "What project did you think would take two hours but took two days?",
    "Do you use fractions or decimals when woodworking?",
    "What woodworking tool has the steepest learning curve?",
    "Which tool deserves the most respect in a woodshop?",
    "What shop storage idea actually worked for you?",
    "How often do you actually clean your shop?",
    "Natural light or lots of LED shop lights?",
    "Show us your scrap wood storage.",
    "What workbench feature gets used the most?",
    "Shop air filtration: worth it or unnecessary?",
    "What size is your workbench?",
    "What project is currently sitting unfinished in your shop?",
    "At what size does a scrap piece become too small to keep?",
    "What woodworking project do customers underestimate the cost of?",
    "What wood makes the biggest mess in your shop?",
    "What\u2019s your best dust-control tip?",
    "Do you fill nail holes or leave them visible?",
    "What\u2019s one thing every woodshop should have?",
    "What popular woodworking trend do you NOT understand?",
    "Table saw, miter saw, or router: which one do you use the most?",
    "Mortise and tenon or dowels?",
    "Safety glasses every time\u2014or only for certain tools?",
    "Dust mask, respirator, or nothing?",
    "What grit do you normally stop sanding at?",
    "Japanese pull saw or Western push saw?",
    "If you could change one thing about your shop, what would it be?",
    "What was the first woodworking project you ever built?",
    "What project almost made you quit woodworking?",
    "Have you ever regretted agreeing to build something for someone?",
    "Hand tools or power tools?",
    "What woodworking project sells the best for you?",
    "What woodworking \u201crule\u201d do you regularly break?",
    "What\u2019s the best woodworking tool under $50?",
    "Hearing protection: plugs or earmuffs?",
    "Tape measure or folding rule?",
    "Do you enjoy sharpening tools or hate it?",
    "Show us your best homemade woodworking jig.",
    "Garage shop, shed shop, basement shop, or dedicated building?",
    "If someone gave you $1,000 for woodworking tools, what\u2019s first on the list?",
    "Have you ever spent longer building the jig than building the project?",
    "What is the most underrated tool on your bench right now?",
    "What hand tool do you struggle with the most?",
    "Live-edge furniture: still cool or played out?",
    "What would your dream woodshop include?",
    "What do you make with your smallest scraps?",
    "What woodworking lesson did you learn the hard way?",
    "How many square feet would your dream shop be?",
    "F-clamps or quick-grip clamps?",
    "Give us your woodworking hot take.",
    "What tool do you secretly want even though you don\u2019t really need it?",
    "What project do you build over and over again?",
    "Have you ever intentionally changed a design because you made a mistake?",
    "What\u2019s the largest woodworking project you\u2019ve ever attempted?",
    "Can you ever have too many clamps?",
    "Post a picture of your first project if you still have it.",
    "How sharp are your chisels right now?",
    "What\u2019s the biggest waste of money in your shop?",
    "What\u2019s currently sitting unfinished in your shop?",
    "Do you sell your woodworking or keep it as a hobby?",
    "What jig should every shop have?",
    "Shop question: do you prefer building with plans, sketches, or figuring it out as you go?",
    "Show us the oldest tool in your shop.",
    "How many unfinished projects do you have right now?",
    "What mistake actually made your project BETTER?",
    "What tool should beginners avoid buying until later?",
    "Do you own any woodworking tools older than you?",
    "What\u2019s the best workbench height?",
    "What tool did you inherit from your dad or grandfather?",
    "What is one safety habit every new woodworker should learn early?",
    "What\u2019s the best woodworking purchase you\u2019ve ever made?",
    "Where does your pencil disappear to every five minutes?",
    "If you could only use hand tools for one project, what would you build?",
    "How big is your woodworking shop?",
    "How many clamps do you own?",
    "What woodworking trend needs to disappear?",
    "What tool do beginners spend too much money on?",
    "Dado joint or pocket hole?",
    "Satin, semi-gloss, or gloss?",
    "Mechanical pencil or carpenter pencil?",
    "Who else has cut a board perfectly\u2014except it was 1 inch too short?",
    "Corded or cordless?",
    "What joint are you currently trying to master?",
    "What brand of sandpaper actually lasts?",
    "What\u2019s your favorite woodworking brand?",
    "What project are you most proud of?",
    "If you could add one tool to your shop today, what would it be?",
    "Water-based or oil-based polyurethane?",
    "What\u2019s your go-to sandpaper grit progression?",
    "If you had to start over, would you choose the same battery platform?",
    "What woodworking mistake will you NEVER make again?",
    "What woodworking mistake taught you the most?",
    "Dominos: worth the price?",
    "If someone gave you $500 for the shop today, what are you buying?",
    "Which woodworking tool is okay to buy cheap?",
    "What is one shop tip you learned the hard way?",
    "What woodworking item do you always seem to run out of?",
    "Show us a project you rescued after thinking it was ruined.",
    "What\u2019s the best shop upgrade you\u2019ve made?",
    "What old-school woodworking technique deserves a comeback?",
    "What\u2019s one safety rule you NEVER break?",
    "What\u2019s your favorite species of wood to work with?",
    "Hardwood or softwood?",
    "What\u2019s the weirdest thing you\u2019ve ever built from wood?",
    "What sharpening system do you use?",
    "Biscuits or dowels?",
    "What saw intimidates beginners the most?",
    "Miter saw or circular saw?",
    "What woodworking tool should you NEVER buy cheap?",
    "What\u2019s one thing every BEGINNER woodworker should buy first?",
    "What tool are you waiting for an excuse to buy?",
    "What project taught you the most?",
    "What saw gets used the most in your shop?",
    "What woodworking project took you way longer than expected?",
    "Wood filler, sawdust and glue, or something else?",
    "What clamp do you reach for most often?",
    "Nails or screws?",
    "Do you build your shop furniture or buy it?",
    "Dog holes: useful or unnecessary?",
    "What cordless platform are you invested in?",
    "Be honest: how big is your scrap pile?",
    "What\u2019s your best measuring tip?",
    "Cabinets or open shelves?",
    "What is a tool you bought cheap but still love?",
    "What woodworking advice do you completely disagree with?",
    "What safety mistake do you see people make too often?",
    "What skill instantly separates an experienced woodworker from a beginner?",
    "Clean shop or organized chaos?",
    "What\u2019s your best trick for making repeated cuts exactly the same?",
    "What\u2019s the best woodworking advice anyone ever gave you?",
    "Oil finish or polyurethane?",
    "What is your favorite wood to work with and why?",
    "What is one clamp, jig, or accessory you reach for constantly?",
    "Mobile tool bases or permanent stations?",
    "Post one project you're proud of and tell us one thing you'd change.",
    "What joint do you avoid whenever possible?",
    "What\u2019s your favorite clamp brand?",
    "What tool brand has treated you best over the years?",
    "Pegboard or French cleat wall?",
    "What is one woodworking tool you wish you had bought sooner?",
    "French cleats\u2014love them or overrated?",
    "Pocket holes: love them or hate them?",
    "Are chisels underrated?",
    "Stain or natural finish?",
    "What\u2019s something experienced woodworkers make look easy?",
    "Epoxy river tables: yes or no?"
];

  var recommendedPosts = {
    Matt: [
      "I keep changing my answer on this: what tool would you replace first if your shop disappeared tomorrow?",
      "What tool did you finally buy and immediately wonder why you waited so long?",
      "I haven't settled this one: track saw or table saw if you could only keep one?",
      "What cheap shop purchase surprised you by becoming indispensable?",
      "What tool looks unnecessary until you actually use one?",
      "What woodworking lesson did you only learn after making the mistake yourself?",
      "I'm curious: which tool in your shop has earned its price ten times over?",
      "What product sounded like hype until you tried it and changed your mind?",
      "What's the one shop upgrade you notice every single time you work?",
      "What tool are you watching for the right price before you finally buy it?"
    ],
    Andy: [
      "My tape measure has entered witness protection again. What disappears most often in your shop?",
      "A clean workbench is beautiful for all six minutes it lasts. Clean shop or organized chaos?",
      "How small does a scrap have to be before you admit you're never using it?",
      "I only need one more clamp. That's how this works, right? How many do you own?",
      "Which tool throws sawdust like it has a personal problem with your shop?",
      "Measure twice, cut once, then stare at the wrong board. What's your most common shop mistake?",
      "What project was supposed to take two hours and quietly stole your entire weekend?",
      "Which tool makes you look busy while you're mostly trying to remember where the pencil went?",
      "Name the tool you defend like you own stock in the company.",
      "What's the strangest scrap you've kept because it was 'too good to throw away'?"
    ],
    "Quick pick": [
      "Corded or cordless?",
      "Build the shop furniture or buy it?",
      "Blade left or blade right?",
      "Track saw or table saw?",
      "Pocket holes or dowels?",
      "Pipe clamps or parallel clamps?",
      "Carpenter pencil or mechanical pencil?",
      "Buy premium once or replace a budget tool later?",
      "Natural finish or stain?",
      "Plans or figure it out as you go?"
    ],
    Community: [
      "Show us the project on your bench right now. Finished is not required.",
      "What's one tool you would recommend to every new woodworker?",
      "What shop tip saved you the most time this year?",
      "What project are you most proud of, and what would you change if you built it again?",
      "What woodworking opinion will you defend every time?",
      "What brand has treated you well enough to earn your loyalty?",
      "What's the best tool under $50 that you actually use?",
      "What homemade jig deserves a permanent spot in your shop?",
      "What skill are you trying to get better at right now?",
      "What old tool still earns its place in your shop?"
    ]
  };

  var lanes = ["Matt", "Andy", "Quick pick", "Community"];
  var pageOffset = 0;

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
    var used = readUsedPosts();
    var ordered = [];
    var round = dayKey(new Date()) + pageOffset / POSTS_TO_SHOW;

    lanes.forEach(function (lane, laneIndex) {
      var choices = recommendedPosts[lane];
      for (var index = 0; index < choices.length; index += 1) {
        var candidate = choices[(round * 3 + laneIndex * 2 + index) % choices.length].slice(0, MAX_LENGTH);
        if (!used.has(candidate)) {
          ordered.push({ text: candidate, voice: lane, style: lane === "Matt" ? "Curiosity" : lane === "Andy" ? "Humor" : "Easy answer" });
          break;
        }
      }
    });

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
    if (!document.getElementById("engagementMoreIdeas")) {
      var more = document.createElement("button");
      more.id = "engagementMoreIdeas";
      more.type = "button";
      more.textContent = "More ideas";
      more.addEventListener("click", function () { pageOffset += POSTS_TO_SHOW; render(); });
      list.parentNode.insertBefore(more, list);
    }
    list.innerHTML = "";
    dailyPosts().forEach(function (post) {
      var text = post.text;
      var item = document.createElement("article");
      item.className = "engagement-post-option";
      var copy = document.createElement("button");
      copy.type = "button";
      copy.textContent = "Copy";
      copy.addEventListener("click", function () { copyText(text, copy); });
      item.innerHTML = '<div class="engagement-post-meta"><span>' + post.voice + '</span><span>' + post.style + '</span></div><label class="engagement-used"><input type="checkbox"><span>Used</span></label><p></p><span>' + text.length + ' characters</span>';
      item.querySelector("p").textContent = text;
      item.querySelector("input").addEventListener("change", function () { markUsed(text); });
      item.appendChild(copy);
      list.appendChild(item);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", render);
  else render();
}());
