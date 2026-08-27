function chunk(array, size) {
  if (size <= 0) {
    throw new Error("size must be a positive integer");
  }
  const chunks = [];
  for (let i = 0; i < array.length; i += size) {
    chunks.push(array.slice(i, i + size));
  }
  return chunks;
}

module.exports = { chunk };
