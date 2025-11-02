import React from "react";
import * as Icons from "lucide-react";
import { LucideIcon } from "lucide-react"; // For type safety

interface DynamicIconProps {
  name: string; // Ensures 'name' is a valid Lucide icon string
  color?: string;
  size?: number;
  className?: string;
}

export const DynamicIcon: React.FC<DynamicIconProps> = ({
  name,
  color = "black",
  size = 16,
  className,
}) => {
  const Icon = Icons[name as keyof typeof Icons] as LucideIcon; // Get the icon component by name

  if (!Icon) {
    console.warn(`Icon "${name}" not found`);
    return null;
  }

  return <Icon color={color} size={size} className={className} />;
};
