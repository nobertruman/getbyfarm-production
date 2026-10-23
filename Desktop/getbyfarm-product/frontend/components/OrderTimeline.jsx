import { orderStatusFlow } from "@/lib/status";

const LABEL = {
  draft: "Approval",
  submitted: "Payment",
  confirmed: "Confirmed",
  processing: "Processing",
  ready_for_dispatch: "Ready",
  in_transit: "In transit",
  delivered: "Delivered",
  completed: "Completed",
  cancelled: "Cancelled",
};

export function OrderTimeline({ status }) {
  if (status === "cancelled") return <p className="text-sm text-berry-500">This order was cancelled.</p>;
  const current = orderStatusFlow.indexOf(status);
  return (
    <ol className="flex items-start overflow-x-auto pb-1">
      {orderStatusFlow.map((step, i) => {
        const done = i <= current;
        return (
          <li key={step} className="flex min-w-[64px] flex-1 flex-col items-center last:flex-none">
            <div className="flex w-full items-center">
              <span
                className={`mx-auto flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 text-[10px] font-medium ${done ? "border-leaf-600 bg-leaf-600 text-white" : "border-line bg-paper text-ink-faint"}`}
              >
                {done ? "✓" : i + 1}
              </span>
              {i < orderStatusFlow.length - 1 && (
                <span className={`h-0.5 flex-1 ${i < current ? "bg-leaf-600" : "bg-line"}`} />
              )}
            </div>
            <span className={`mt-1.5 text-center text-[11px] ${done ? "text-ink" : "text-ink-faint"}`}>
              {LABEL[step]}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
