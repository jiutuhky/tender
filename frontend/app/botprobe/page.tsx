import { notFound } from "next/navigation";
import { BotProbe } from "./_components/BotProbe";

export default function BotProbePage() {
  if (process.env.NODE_ENV !== "development") notFound();
  return <BotProbe />;
}
