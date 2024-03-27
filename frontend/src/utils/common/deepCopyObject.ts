export const deepCopyObject = <T extends Record<string, any>>(obj: T): T => {
  const newObj = { ...obj };
  for (const key in newObj) {
    if (Array.isArray(obj[key])) {
      newObj[key] = newObj[key].map((item: any) => {
        if (typeof item === 'object') {
          return deepCopyObject(item);
        }
        return item;
      });
    } else if (typeof newObj[key] === 'object') {
      newObj[key] = deepCopyObject(newObj[key]);
    }
  }

  return newObj;
};
