// "use client"; // Marks this as a Client Component

// import { useState } from "react";
// import { useJobProgress } from "@/hooks/events/useJobProgress";
// import { useUser } from "@/features/auth/UserContext";
import { caller } from "@/lib/trpc/server";

export default async function Page() {
  // const [notifications, setNotifications] = useState<string[]>([]);
  // const progress = useJobProgress("abc");
  // const user = useUser();
  const events = await caller.analytics.getEventsForEntity({
    entity: "CHINA",
  });
  return (
    <div>
      {/*<h3>Real-time Notifications:</h3>*/}
      {/*<ul>{progress}</ul>*/}
      {/*<p>{user.id}</p>*/}
      {events.map((e, i) => (
        <div key={i}>
          {e.value} {e.count}
          {e.events.map((event, j) => (
            <div key={j}>
              {event.sentence} <br />
              {event.text} {event.A0} {event.A1} {event.LOC}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
