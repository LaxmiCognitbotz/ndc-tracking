interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const getStatusStyle = (status: string) => {
    const normalized = status.toLowerCase();
    if (normalized === "completed") {
      return "bg-green-50 text-green-700 border-green-200";
    } else if (normalized === "pending") {
      return "bg-red-50 text-red-700 border-red-200";
    } else if (normalized === "in progress") {
      return "bg-orange-50 text-orange-700 border-orange-200";
    } else if (normalized === "not applicable") {
      return "bg-gray-50 text-gray-500 border-gray-200";
    }
    return "bg-gray-50 text-gray-700 border-gray-200";
  };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getStatusStyle(status)}`}>
      {status}
    </span>
  );
}
