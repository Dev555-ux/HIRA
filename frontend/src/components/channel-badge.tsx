import { Badge } from "@/components/ui/badge";
import { CHANNELS, DEFAULT_CHANNEL, type Channel } from "@/lib/channels";

export function ChannelBadge({ channel = DEFAULT_CHANNEL }: { channel?: Channel }) {
  const { label, icon: Icon } = CHANNELS[channel];
  return (
    <Badge variant="outline" className="gap-1 font-normal text-muted-foreground">
      <Icon className="size-3" />
      {label}
    </Badge>
  );
}
