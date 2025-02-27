export default function newPointIndicator(number: number, color: string, showNumber: boolean) {
  const container = document.createElement("div");
  container.style.position = "relative";
  container.style.zIndex = "2";

  const dot = document.createElement("div");
  dot.style.width = "5px";
  dot.style.height = "5px";
  dot.style.backgroundColor = color || "red";
  dot.style.borderRadius = "50%";
  dot.style.position = "absolute";
  dot.style.bottom = "0";
  dot.style.left = "0";
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