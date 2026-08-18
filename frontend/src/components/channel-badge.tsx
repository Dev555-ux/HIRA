import { Badge } from "@/components/ui/badge";
import { CHANNELS, DEFAULT_CHANNEL, type Channel } from "@/lib/channels";

export function ChannelBadge({ channel = DEFAULT_CHANNEL }: { channel?: Channel }) {
  // Falls back rather than crashing the inbox render if the backend ever
  // sends a channel string this frontend doesn't know about yet (a new
  // channel shipped backend-first, same staged-rollout order this whole
  // Instagram effort has followed).
  const { label, icon: Icon } = CHANNELS[channel] ?? CHANNELS[DEFAULT_CHANNEL];
  return (
    <Badge variant="outline" className="gap-1 font-normal text-muted-foreground">
      <Icon className="size-3" />
      {label}
    </Badge>
  );
}
