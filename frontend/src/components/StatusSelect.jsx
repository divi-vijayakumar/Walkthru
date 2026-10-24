import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { STATUSES } from "@/lib/api";
import { LEAD } from "@/constants/testIds";

export const StatusSelect = ({ value, onChange, disabled }) => (
  <Select value={value} onValueChange={onChange} disabled={disabled}>
    <SelectTrigger
      data-testid={LEAD.statusSelect}
      className="h-10 w-44 border-zinc-700 bg-zinc-900 text-sm text-zinc-100 focus:ring-orange-500"
    >
      <SelectValue />
    </SelectTrigger>
    <SelectContent className="border-zinc-700 bg-zinc-900 text-zinc-100">
      {Object.entries(STATUSES).map(([key, s]) => (
        <SelectItem key={key} value={key} data-testid={LEAD.statusOption(key)} className="focus:bg-zinc-800 focus:text-zinc-50">
          {s.label}
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
);
