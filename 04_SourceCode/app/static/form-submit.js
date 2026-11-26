// Quản lý gửi biểu mẫu, menu, hiện/ẩn mật khẩu, in và chọn tuần lịch.
document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!form.matches("[data-single-submit]")) return;
  if (form.dataset.submitting || (form.dataset.confirm && !window.confirm(form.dataset.confirm))) {
    event.preventDefault();
    return;
  }
  form.dataset.submitting = "1";
  const button = event.submitter || form.querySelector('button[type="submit"]');
  if (button) {
    button.dataset.originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = "Đang xử lý…";
  }
});

window.addEventListener("pageshow", (event) => {
  if (!event.persisted) return;
  for (const form of document.querySelectorAll("[data-single-submit][data-submitting]")) {
    delete form.dataset.submitting;
    for (const button of form.querySelectorAll("[data-original-label]")) {
      button.disabled = false;
      button.textContent = button.dataset.originalLabel;
      delete button.dataset.originalLabel;
    }
  }
});

const menuToggle = document.querySelector(".menu-toggle");
if (menuToggle) {
  const menu = document.getElementById(menuToggle.getAttribute("aria-controls"));
  const compact = window.matchMedia("(max-width: 900px)");
  const desktopToggle = document.querySelector(".desktop-toggle");
  const shell = menuToggle.closest(".shell");
  let collapsed = false;
  try { collapsed = sessionStorage.getItem("ironpulse-nav-collapsed") === "true"; } catch {}
  const updateMenu = (open) => {
    menuToggle.hidden = !compact.matches;
    menuToggle.setAttribute("aria-expanded", String(open));
    menu.hidden = compact.matches && !open;
    if (desktopToggle) {
      desktopToggle.hidden = compact.matches;
      desktopToggle.setAttribute("aria-expanded", String(!collapsed));
      desktopToggle.setAttribute("aria-label", collapsed ? "Mở rộng điều hướng" : "Thu gọn điều hướng");
      desktopToggle.querySelector("span").textContent = collapsed ? "Mở rộng" : "Thu gọn";
    }
    shell.classList.toggle("nav-collapsed", !compact.matches && collapsed);
  };
  menuToggle.addEventListener("click", () => updateMenu(menuToggle.getAttribute("aria-expanded") !== "true"));
  menu.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && compact.matches) {
      updateMenu(false);
      menuToggle.focus();
    }
  });
  compact.addEventListener("change", () => updateMenu(false));
  desktopToggle?.addEventListener("click", () => {
    collapsed = !collapsed;
    try { sessionStorage.setItem("ironpulse-nav-collapsed", String(collapsed)); } catch {}
    updateMenu(false);
  });
  updateMenu(false);
}

const account = document.querySelector(".account-menu");
if (account) {
  account.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && account.open) {
      account.open = false;
      account.querySelector("summary").focus();
    }
  });
  document.addEventListener("click", (event) => {
    if (account.open && !account.contains(event.target)) account.open = false;
  });
}

for (const button of document.querySelectorAll("[data-password-reveal]")) {
  const input = document.getElementById(button.getAttribute("aria-controls"));
  if (!input) continue;
  button.hidden = false;
  const hide = () => {
    input.type = "password";
    button.textContent = "Hiện";
    button.setAttribute("aria-label", "Hiện mật khẩu");
  };
  button.addEventListener("click", () => {
    if (input.type === "text") {
      hide();
    } else {
      input.type = "text";
      button.textContent = "Ẩn";
      button.setAttribute("aria-label", "Ẩn mật khẩu");
    }
  });
  input.form.addEventListener("submit", hide);
  window.addEventListener("pagehide", hide);
}

for (const button of document.querySelectorAll("[data-print]")) {
  button.hidden = false;
  button.addEventListener("click", () => window.print());
}

for (const agenda of document.querySelectorAll("[data-agenda]")) {
  const days = Array.from(agenda.querySelectorAll("[data-week]"));
  const controls = agenda.querySelector(".week-tools");
  const select = controls.querySelector("select");
  for (const entry of days) {
    const week = entry.dataset.week;
    if (!Array.from(select.options).some((option) => option.value === week)) {
      const [year, number] = week.split("-W");
      select.add(new Option(`Tuần ${number}/${year}`, week));
    }
  }
  controls.hidden = days.length === 0;
  const showWeek = () => {
    for (const entry of days) entry.hidden = !!select.value && entry.dataset.week !== select.value;
  };
  select.addEventListener("change", showWeek);
  if (Array.from(select.options).some(option => option.value === agenda.dataset.selectedWeek)) {
    select.value = agenda.dataset.selectedWeek;
    showWeek();
  }
}
