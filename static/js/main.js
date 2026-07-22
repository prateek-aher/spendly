// main.js — students will add JavaScript here as features are built

function scheduleFlashRemoval(flash) {
    const MIN_DURATION_MS = 3000;
    const MAX_DURATION_MS = 10000;
    const MS_PER_CHARACTER = 60;

    const length = flash.textContent.trim().length;
    const duration = Math.min(
        MAX_DURATION_MS,
        Math.max(MIN_DURATION_MS, length * MS_PER_CHARACTER)
    );

    setTimeout(() => {
        flash.classList.add("flash-hide");
        flash.addEventListener("transitionend", () => flash.remove(), { once: true });
    }, duration);
}

function toLocalIsoDate(d) {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function setupNavToggle() {
    const toggle = document.getElementById("nav-toggle");
    const nav = document.getElementById("nav-links");
    if (!toggle || !nav) return;

    function closeMenu() {
        nav.classList.remove("is-open");
        toggle.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
    }

    function openMenu() {
        nav.classList.add("is-open");
        toggle.classList.add("is-open");
        toggle.setAttribute("aria-expanded", "true");
    }

    toggle.addEventListener("click", () => {
        if (nav.classList.contains("is-open")) {
            closeMenu();
        } else {
            openMenu();
        }
    });

    nav.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMenu));

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeMenu();
    });

    document.addEventListener("click", (event) => {
        if (!nav.classList.contains("is-open")) return;
        if (nav.contains(event.target) || toggle.contains(event.target)) return;
        closeMenu();
    });
}

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".flash").forEach(scheduleFlashRemoval);

    document.querySelectorAll("form[data-confirm]").forEach((form) => {
        form.addEventListener("submit", (event) => {
            if (!window.confirm(form.dataset.confirm)) {
                event.preventDefault();
            }
        });
    });

    setupNavToggle();

    const expenseForm = document.getElementById("expense-form");
    if (!expenseForm) return;

    expenseForm.querySelectorAll(".date-quick-pick").forEach((btn) => {
        btn.addEventListener("click", () => {
            const dateInput = document.getElementById("date");
            const d = new Date();
            d.setDate(d.getDate() - Number(btn.dataset.daysAgo));
            dateInput.value = toLocalIsoDate(d);
        });
    });

    const errorField = expenseForm.dataset.errorField;
    if (errorField) {
        const target = errorField === "category"
            ? expenseForm.querySelector('input[name="category"]')
            : document.getElementById(errorField);
        if (target) target.focus();
    }
});
