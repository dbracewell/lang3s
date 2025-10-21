export const capitalize = (text: string, allWords: boolean = false) => {
   return text
      .split(/[\s_]+/g)
      .map((word, idx) => {
         if (allWords || idx === 0) {
            return word[0].toUpperCase() + word.slice(1);
         }
         return word;
      })
      .join(" ");
};
