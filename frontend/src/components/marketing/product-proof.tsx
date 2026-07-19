import { Calendar, CheckCheck } from "lucide-react";

// Shows the product instead of describing it: a real WhatsApp exchange from
// question to confirmed booking, readable in under five seconds. Sits
// immediately below Hero so the promise HIRA just made is proven before the
// visitor scrolls any further. Static by design — no animation to wait on.
export function ProductProof() {
  return (
    <section className="mx-auto max-w-6xl px-4 pb-16 sm:px-6 sm:pb-24">
      <h2 className="text-center text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        See it in action
      </h2>

      <div className="mx-auto mt-6 w-full max-w-md rounded-2xl border bg-card p-4 shadow-lg sm:p-5">
        <div className="flex items-center gap-2 border-b pb-3">
          <span className="size-2 rounded-full bg-success" />
          <span className="text-xs font-medium text-muted-foreground">
            WhatsApp · Riverside Dental
          </span>
        </div>

        <div className="mt-4 flex flex-col gap-3">
          <div className="max-w-[85%] rounded-2xl rounded-bl-sm bg-secondary px-3.5 py-2 text-sm">
            Hi, do you have anything free tomorrow afternoon for a cleaning?
          </div>

          <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-3.5 py-2 text-sm text-primary-foreground">
            Yes — 2:30pm or 4pm tomorrow. Which works better?
          </div>

          <div className="max-w-[85%] rounded-2xl rounded-bl-sm bg-secondary px-3.5 py-2 text-sm">
            4pm please
          </div>

          <div className="ml-auto flex max-w-[85%] items-center gap-2 rounded-2xl rounded-br-sm bg-primary px-3.5 py-2 text-sm text-primary-foreground">
            <Calendar className="size-4 shrink-0" aria-hidden="true" />
            Booked for 4:00pm tomorrow. See you then!
          </div>
        </div>

        <div className="mt-4 flex items-center gap-1.5 border-t pt-3 text-xs text-muted-foreground">
          <CheckCheck className="size-3.5 shrink-0 text-success" aria-hidden="true" />
          Sent by HIRA · approved in Assisted Mode
        </div>
      </div>
    </section>
  );
}
