// Production console guard.
// - Silences console.log/info/debug so debug output never reaches users' DevTools.
// - Keeps console.warn/error, but reduces axios errors to { message, status, detail }.
//   A raw axios error carries config.headers (Bearer token) and config.data
//   (request body, e.g. LMS password/cookies), so it must never be printed whole.

const summarize = (arg) => {
  if (arg && arg.isAxiosError) {
    return {
      message: arg.message,
      status: arg.response?.status,
      detail: arg.response?.data?.detail,
    };
  }
  return arg;
};

if (process.env.NODE_ENV === 'production') {
  const noop = () => {};
  console.log = noop;
  console.info = noop;
  console.debug = noop;

  const originalError = console.error.bind(console);
  const originalWarn = console.warn.bind(console);
  console.error = (...args) => originalError(...args.map(summarize));
  console.warn = (...args) => originalWarn(...args.map(summarize));
}
