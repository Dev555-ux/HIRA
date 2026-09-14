/** One heading + body block, reused across every legal page so a reader
 * gets the same rhythm on Privacy as on Terms as on Data Deletion — this is
 * the one shared visual unit those documents actually need; everything else
 * is just <p>/<ul> inside it. */
export function LegalSection({
  id,
  title,
  children,
}: {
  id?: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="mt-10 scroll-mt-24 first:mt-0">
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <div className="mt-3 space-y-4 text-sm leading-relaxed text-muted-foreground sm:text-base [&_a]:text-foreground [&_a]:underline [&_a]:underline-offset-2 [&_li]:pl-1 [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-6">
        {children}
      </div>
    </section>
  );
}
