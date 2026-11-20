import { useState } from "react";

export default function InlineForm({ label, placeholder, submit, type = "text", onSubmit, hint, successText }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      await onSubmit(value);
      setValue("");
      setDone(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const hintText = hint?.(value);
  return (
    <form className="inline" onSubmit={handleSubmit}>
      <label>
        {label}
        <input
          type={type}
          value={value}
          placeholder={placeholder}
          required
          onChange={(event) => {
            setValue(event.target.value);
            setDone(false);
          }}
        />
      </label>
      {hintText && <small>{hintText}</small>}
      <button type="submit" disabled={busy}>
        {submit}
      </button>
      {done && successText && <small role="status">{successText}</small>}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </form>
  );
}