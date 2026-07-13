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

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".flash").forEach(scheduleFlashRemoval);

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
