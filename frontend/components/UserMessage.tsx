export default function UserMessage({ text }: { text: string }) {
  return (
    <div className="turn turn-user">
      <div className="bubble-user">{text}</div>
    </div>
  );
}
