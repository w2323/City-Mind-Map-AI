export function createMutationQueue() {
  let tail=Promise.resolve();
  return {run(operation) {
    const result=tail.then(operation);
    tail=result.catch(()=>{});
    return result;
  }};
}
