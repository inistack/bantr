export default function Members({ members, online }) {
  const onlineIds = new Set(online);
  const ordered = [...members].sort(
    (a, b) =>
      Number(onlineIds.has(b.id)) - Number(onlineIds.has(a.id)) || a.name.localeCompare(b.name),
  );
  return (
    <ul className="members">
      {ordered.map((m) => {
        const isOnline = onlineIds.has(m.id);
        return (
          <li key={m.id}>
            <span
              role="img"
              aria-label={isOnline ? "online" : "offline"}
              className={isOnline ? "dot on" : "dot off"}
            >
              {isOnline ? "●" : "○"}
            </span>
            {m.name} <small>{m.role}</small>
          </li>
        );
      })}
    </ul>
  );
}