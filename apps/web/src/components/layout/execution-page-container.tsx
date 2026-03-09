import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type ExecutionPageContainerProps = {
  children: ReactNode;
  className?: string;
};

export function ExecutionPageContainer({ children, className }: ExecutionPageContainerProps) {
  return <section className={cn("mx-auto w-full max-w-[1200px] space-y-6", className)}>{children}</section>;
}
