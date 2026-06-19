import { LucideIcon } from "lucide-react";

interface KPICardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  colorClass: string;
  bgClass?: string;
}

export function KPICard({ title, value, icon: Icon, colorClass }: KPICardProps) {
  return (
    <div className="bg-card rounded-[4px] p-6 border border-border h-[120px] flex flex-col justify-between">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm text-muted-foreground leading-tight">{title}</p>
        <Icon className={`w-6 h-6 flex-shrink-0 ${colorClass}`} />
      </div>
      <p className={`text-3xl font-bold ${colorClass}`}>{value}</p>
    </div>
  );
}
