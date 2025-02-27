import React from "react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./tooltip";
import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface TooltipIconProps {
  icon: LucideIcon;
  tooltipText: string;
  onClick: () => void;
  isActive?: boolean;
  className?: string;
  iconSize?: number;
}

const TooltipIcon: React.FC<TooltipIconProps> = ({
  icon: Icon,
  tooltipText,
  onClick,
  isActive = false,
  className = "",
  iconSize = 20
}) => {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            onClick={onClick}
            className={cn(
              "p-2 rounded-md transition-colors",
              isActive ? "bg-white shadow-sm" : "hover:bg-gray-200",
              className
            )}
          >
            <Icon size={iconSize} />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <p>{tooltipText}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default TooltipIcon;
