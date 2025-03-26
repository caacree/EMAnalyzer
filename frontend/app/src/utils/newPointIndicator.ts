export default function newPointIndicator(number: number, color: string, showNumber: boolean) {
  const container = document.createElement("div");
  container.style.position = "relative";
  container.style.zIndex = "2";
  // Center the container by shifting it 50% left and up.

  const dot = document.createElement("div");
  dot.style.width = "6px";
  dot.style.height = "6px";
  dot.style.backgroundColor = color || "red";
  dot.style.borderRadius = "50%";
  dot.style.position = "absolute";
  dot.style.bottom = "-3px";
  dot.style.left = "-3px";
  container.appendChild(dot);

  if (showNumber) {
    const numberLabel = document.createElement("div");
    numberLabel.innerText = number.toString();
    numberLabel.style.color = color || "red";
    numberLabel.style.position = "absolute";
    numberLabel.style.top = "-10px";
    numberLabel.style.left = "10px";
    container.appendChild(numberLabel);
  }
  return container;
}
