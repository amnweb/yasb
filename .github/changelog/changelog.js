module.exports = {
    types: [
      { types: ["feat", "feature"], label: "New Features" },
      { types: ["fix", "bugfix"], label: "Bugfixes" },
      { types: ["improvements", "enhancement"], label: "Improvements" },
      { types: ["perf"], label: "Performance Improvements" },
      { types: ["build", "ci"], label: "Build System" },
      { types: ["refactor"], label: "Refactors" },
      { types: ["doc", "docs"], label: "Documentation Changes" },
      { types: ["test", "tests"], label: "Tests" },
      { types: ["style"], label: "Code Style Changes" },
      { types: ["chore"], label: "Chores" },
      { types: ["other"], label: "Other Changes" },
    ],
  
    renderTypeSection: function (label, commits) {
      let text = `\n### ${label}\n`;
      commits.forEach(commit => {
        text += `- ${commit.subject} ${commit.url}\n`;
      });
      return text;
    }
  };