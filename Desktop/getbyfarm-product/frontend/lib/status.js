export const orderStatusFlow = [
  "draft",
  "submitted",
  "confirmed",
  "processing",
  "ready_for_dispatch",
  "in_transit",
  "delivered",
  "completed",
];

export const STATUS_LABEL = {
  draft: "Awaiting approval",
  submitted: "Awaiting payment",
  confirmed: "Paid · confirmed",
  processing: "Processing",
  ready_for_dispatch: "Ready for dispatch",
  in_transit: "In transit",
  delivered: "Delivered",
  completed: "Completed",
  cancelled: "Cancelled",
};
