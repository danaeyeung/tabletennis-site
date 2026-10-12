// 世界排名页面：标签页切换
document.addEventListener("DOMContentLoaded", function () {
  var tabBtns = document.querySelectorAll(".tab-btn");
  var panels = document.querySelectorAll(".tab-panel");

  tabBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var target = btn.getAttribute("data-tab");

      tabBtns.forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");

      panels.forEach(function (p) {
        p.classList.toggle("active", p.id === target);
      });

      // 同步地址 hash，便于直接分享某个分项链接
      if (history.replaceState) {
        history.replaceState(null, "", "#" + target);
      }
    });
  });

  // 若 URL 带 #tab-women 之类的锚点，打开对应标签
  var hash = window.location.hash.replace("#", "");
  if (hash) {
    var matched = false;
    tabBtns.forEach(function (b) {
      if (b.getAttribute("data-tab") === hash) {
        b.click();
        matched = true;
      }
    });
    if (!matched && tabBtns[0]) tabBtns[0].click();
  }
});
