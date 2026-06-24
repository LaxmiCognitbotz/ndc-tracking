import { Loader2 } from "lucide-react";

export function LoadingScreen() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] w-full h-full p-8">
      {/* Animated Company Logo Placeholder */}
      <div className="relative flex items-center justify-center w-24 h-24 mb-6">
        <div className="absolute inset-0 bg-primary/20 rounded-full animate-ping"></div>
        <div className="relative bg-primary text-primary-foreground rounded-full p-4 shadow-lg shadow-primary/25">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="40"
            height="40"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="animate-pulse"
          >
            <rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect>
            <path d="M9 22v-4h6v4"></path>
            <path d="M8 6h.01"></path>
            <path d="M16 6h.01"></path>
            <path d="M12 6h.01"></path>
            <path d="M12 10h.01"></path>
            <path d="M12 14h.01"></path>
            <path d="M16 10h.01"></path>
            <path d="M16 14h.01"></path>
            <path d="M8 10h.01"></path>
            <path d="M8 14h.01"></path>
          </svg>
        </div>
      </div>
      <h3 className="text-xl font-bold text-foreground">Loading Dashboard</h3>
      <p className="text-muted-foreground flex items-center gap-2 mt-2">
        <Loader2 className="w-4 h-4 animate-spin text-primary" />
        Processing data securely...
      </p>
    </div>
  );
}
