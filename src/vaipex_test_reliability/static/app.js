const button = document.querySelector("#complete-order");
const result = document.querySelector("#checkout-result");
const title = document.querySelector("[data-result-title]");
const detail = document.querySelector("[data-result-detail]");

button?.addEventListener("click", async () => {
  button.disabled = true;
  button.textContent = "Processing…";
  result.hidden = true;

  const scenario = document.body.dataset.scenario;
  const response = await fetch(`/api/checkout?scenario=${encodeURIComponent(scenario)}`, {
    method: "POST",
  });
  const payload = await response.json();

  result.className = `result ${response.ok ? "success" : "failure"}`;
  title.textContent = payload.message;
  detail.textContent = response.ok
    ? `Confirmation ${payload.order_id} · attempt ${payload.attempt}`
    : `Attempt ${payload.attempt} preserved as ${payload.outcome}`;
  result.hidden = false;
  button.disabled = false;
  button.textContent = response.ok ? "Order complete" : "Try checkout again";
});
