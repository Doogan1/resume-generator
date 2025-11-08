const state = {
  projects: [],
  skills: {},
  experience: [],
  jobs: [],
  summaries: [],
  selectedProjectId: null,
  selectedJobSlug: null,
  currentJob: null,
  resumeGenerations: [],
  selectedResumeId: null,
  currentResume: null,
  prompts: {
    project_extra_instruction: "",
    resume_extra_instruction: "",
    cover_letter_extra_instruction: "",
  },
};

const viewFns = {
  projects: renderProjectsView,
  skills: renderSkillsView,
  jobs: renderJobsView,
  resume: renderResumeView,
  settings: renderSettingsView,
};

const container = document.getElementById("view-container");
const statusEl = document.getElementById("status-message");

document.querySelectorAll(".tab-button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab-button").forEach((btn) => btn.classList.remove("active"));
    button.classList.add("active");
    renderView(button.dataset.view);
  });
});

async function init() {
  try {
    await Promise.all([
      loadProjects(),
      loadSkills(),
      loadExperience(),
      loadJobs(),
      loadSummaries(),
      loadResumeGenerations(),
      loadPrompts(),
    ]);
    renderView("projects");
  } catch (error) {
    setStatus(error.message || "Failed to load initial data", true);
  }
}

function renderView(view) {
  const fn = viewFns[view];
  if (!fn) return;
  fn();
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
function setStatus(message, isError = false) {
  if (!statusEl) return;
  statusEl.textContent = message;
  statusEl.classList.toggle("error-text", Boolean(isError));
}

async function apiRequest(path, options = {}) {
  const opts = { ...options };
  opts.headers = opts.headers ? { ...opts.headers } : {};
  if (opts.body && !opts.headers["Content-Type"]) {
    opts.headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, opts);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const err = await response.json();
      message = err?.error?.message || message;
    } catch (_) {
      // ignore
    }
    throw new Error(message);
  }
  return response.json();
}

async function loadProjects() {
  const { data } = await apiRequest("/api/projects");
  state.projects = data || [];
}

async function loadSkills() {
  const { data } = await apiRequest("/api/skills");
  state.skills = data || {};
}

async function loadExperience() {
  const { data } = await apiRequest("/api/experience");
  state.experience = data || [];
}

async function loadJobs() {
  const { data } = await apiRequest("/api/jobs");
  state.jobs = data || [];
}

async function loadSummaries() {
  const { data } = await apiRequest("/api/summaries");
  state.summaries = data || [];
}

async function loadPrompts() {
  const { data } = await apiRequest("/api/prompts");
  state.prompts = data || state.prompts;
}

async function loadResumeGenerations() {
  const { data } = await apiRequest("/api/ai/resumes");
  state.resumeGenerations = data || [];
}

async function loadResumeDetail(resumeId) {
  const { data } = await apiRequest(`/api/ai/resumes/${resumeId}`);
  state.currentResume = data || null;
  return state.currentResume;
}

async function requestCoverLetter(resumeId, { instructions = "", coverLetter = null } = {}) {
  const body = {};
  if (coverLetter !== null) {
    body.cover_letter = coverLetter;
  } else {
    body.instructions = instructions;
  }
  const { data } = await apiRequest(`/api/ai/resumes/${resumeId}/cover-letter`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return data;
}

async function saveResumeHtml(resumeId, resumeHtml) {
  const { data } = await apiRequest(`/api/ai/resumes/${resumeId}/resume`, {
    method: "PUT",
    body: JSON.stringify({ resume_html: resumeHtml }),
  });
  return data;
}

async function saveResumeMetadata(resumeId, updates) {
  const { data } = await apiRequest(`/api/ai/resumes/${resumeId}`, {
    method: "PUT",
    body: JSON.stringify(updates),
  });
  return data;
}

async function exportResumePdfs(resumeId) {
  const { data } = await apiRequest(`/api/ai/resumes/${resumeId}/export`, {
    method: "POST",
  });
  return data;
}

async function savePrompts(updates) {
  const { data } = await apiRequest("/api/prompts", {
    method: "PUT",
    body: JSON.stringify(updates),
  });
  state.prompts = data || state.prompts;
  return state.prompts;
}

// ---------------------------------------------------------------------------
// Projects dashboard
// ---------------------------------------------------------------------------
function projectById(projectId) {
  return state.projects.find((project) => project.id === projectId);
}

function renderProjectsView() {
  const selected = state.selectedProjectId ? projectById(state.selectedProjectId) : null;
  container.innerHTML = `
    <section class="pane grid two">
      <div>
        <div class="button-row" style="justify-content: space-between; align-items: center;">
          <h2>Projects</h2>
          <button class="secondary" id="new-project-btn">New Project</button>
        </div>
        <ul class="list" id="project-list">
          ${state.projects
            .map(
              (project) => `
                <li>
                  <button data-project-id="${project.id}" class="${
                    project.id === state.selectedProjectId ? "active" : ""
                  }">
                    <strong>${project.name || "(Untitled)"}</strong><br>
                    <small>${project.year || "Year N/A"}</small>
                  </button>
                </li>`
            )
            .join("")}
        </ul>
      </div>
      <div id="project-form-container">
        ${selected ? projectFormHtml(selected) : "<p>Select a project to edit, or create a new one.</p>"}
      </div>
    </section>

    <section class="pane">
      <div class="button-row" style="justify-content: space-between; align-items: center;">
        <h2>Experience</h2>
        <button class="secondary" id="new-experience-btn">Add Experience</button>
      </div>
      <div id="experience-editor">
        ${state.experience.map(experienceFormHtml).join("")}
      </div>
    </section>
  `;

  // Event bindings
  container.querySelectorAll("[data-project-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedProjectId = button.dataset.projectId;
      renderProjectsView();
    });
  });

  const newProjectBtn = container.querySelector("#new-project-btn");
  if (newProjectBtn) {
    newProjectBtn.addEventListener("click", () => {
      state.selectedProjectId = null;
      renderProjectCreationForm();
    });
  }

  const newExperienceBtn = container.querySelector("#new-experience-btn");
  if (newExperienceBtn) {
    newExperienceBtn.addEventListener("click", () => renderExperienceCreationForm());
  }

  if (selected) {
    bindProjectForm(selected);
  }
  bindExperienceForms();
}

function projectFormHtml(project) {
  return `
    <form id="project-form">
      <h2>Edit Project</h2>
      <label>Name</label>
      <input type="text" name="name" value="${project.name || ""}" required>

      <label>Year</label>
      <input type="text" name="year" value="${project.year || ""}" placeholder="2024">

      <label>Short Description</label>
      <textarea name="description_short" placeholder="One-line summary">${project.description_short || ""}</textarea>

      <label>Bullets (one per line)</label>
      <textarea name="bullets">${(project.bullets || []).join("\n")}</textarea>

      <label>Skills Used</label>
      <div class="skills-checkboxes">
        ${skillsCheckboxes(project.skills_used || [])}
      </div>

      <label>Linked Experience</label>
      <div class="skills-checkboxes">
        ${experienceCheckboxes(project.linked_experience || [])}
      </div>

      <label>AI Prompt Context</label>
      <textarea name="ai_context" placeholder="Paste raw notes, metrics, or snippets for the AI helper"></textarea>

      <div class="button-row">
        <button type="submit" class="primary">Save Project</button>
        <button type="button" class="secondary" data-action="ai-generate">AI Rewrite</button>
        <button type="button" class="secondary" id="delete-project-btn">Delete Project</button>
      </div>
    </form>
  `;
}

function renderProjectCreationForm() {
  const formContainer = container.querySelector("#project-form-container");
  formContainer.innerHTML = `
    <form id="project-form">
      <h2>New Project</h2>
      <label>Name</label>
      <input type="text" name="name" placeholder="Project name" required>

      <label>Year</label>
      <input type="text" name="year" placeholder="2024">

      <label>Short Description</label>
      <textarea name="description_short" placeholder="One-line summary"></textarea>

      <label>Bullets (one per line)</label>
      <textarea name="bullets" placeholder="What did you deliver?"></textarea>

      <label>Skills Used</label>
      <div class="skills-checkboxes">
        ${skillsCheckboxes([])}
      </div>

      <label>Linked Experience</label>
      <div class="skills-checkboxes">
        ${experienceCheckboxes([])}
      </div>

      <label>AI Prompt Context</label>
      <textarea name="ai_context" placeholder="Paste raw notes, metrics, or snippets for the AI helper"></textarea>

      <div class="button-row">
        <button type="submit" class="primary">Create Project</button>
        <button type="button" class="secondary" data-action="ai-generate">Draft with AI</button>
      </div>
    </form>
  `;
  bindProjectForm(null);
}

function skillsCheckboxes(selected) {
  const selectedSet = new Set(selected);
  return Object.entries(state.skills)
    .map(
      ([category, entries]) => `
        <div>
          <strong>${category}</strong>
          ${entries
            .map(
              (entry) => `
                <label>
                  <input type="checkbox" name="project-skill" value="${entry.id}" ${
                    selectedSet.has(entry.id) ? "checked" : ""
                  }>
                  ${entry.label}
                </label>`
            )
            .join("")}
        </div>`
    )
    .join("");
}

function experienceCheckboxes(selected) {
  const selectedSet = new Set(selected);
  return state.experience
    .map(
      (exp) => `
        <label>
          <input type="checkbox" name="project-experience" value="${exp.id}" ${
            selectedSet.has(exp.id) ? "checked" : ""
          }>
          ${exp.company} — ${exp.title}
        </label>`
    )
    .join("");
}

function bindProjectForm(project) {
  const form = container.querySelector("#project-form");
  if (!form) return;

  const aiButton = form.querySelector('[data-action="ai-generate"]');
  if (aiButton) {
    aiButton.addEventListener("click", async () => {
      const contextField = form.querySelector('[name="ai_context"]');
      const context = contextField ? contextField.value.trim() : "";
      if (!context) {
        setStatus("Provide AI context before requesting a draft.", true);
        return;
      }
      aiButton.disabled = true;
      setStatus("Requesting AI assistance...");
      try {
        const payload = { context };
        if (project && project.id) {
          payload.project_id = project.id;
        }
        const response = await apiRequest("/api/ai/projects", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        const { data: projectData, meta } = response;
        await Promise.all([loadProjects(), loadSkills()]);
        state.selectedProjectId = projectData.id;
        setStatus(
          meta?.action === "created"
            ? `AI created project "${projectData.name}".`
            : `AI updated project "${projectData.name}".`
        );
        renderProjectsView();
      } catch (error) {
        setStatus(error.message, true);
      } finally {
        aiButton.disabled = false;
      }
    });
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const payload = {
      name: formData.get("name"),
      year: formData.get("year"),
      description_short: formData.get("description_short"),
      bullets: (formData.get("bullets") || "")
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      skills_used: formData.getAll("project-skill"),
      linked_experience: formData.getAll("project-experience"),
    };

    try {
      if (project) {
        await apiRequest(`/api/projects/${project.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        setStatus(`Updated project "${payload.name}".`);
      } else {
        const { data } = await apiRequest("/api/projects", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        state.selectedProjectId = data.id;
        setStatus(`Created project "${payload.name}".`);
      }
      await loadProjects();
      renderProjectsView();
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  const deleteBtn = container.querySelector("#delete-project-btn");
  if (deleteBtn && project) {
    deleteBtn.addEventListener("click", async () => {
      if (!confirm(`Delete project "${project.name}"?`)) return;
      try {
        await apiRequest(`/api/projects/${project.id}`, { method: "DELETE" });
        state.selectedProjectId = null;
        await loadProjects();
        setStatus(`Deleted project "${project.name}".`);
        renderProjectsView();
      } catch (error) {
        setStatus(error.message, true);
      }
    });
  }
}

function experienceFormHtml(exp) {
  return `
    <form class="experience-form" data-experience-id="${exp.id}">
      <label>Company</label>
      <input type="text" name="company" value="${exp.company || ""}" required>

      <label>Title</label>
      <input type="text" name="title" value="${exp.title || ""}" required>

      <label>Dates</label>
      <input type="text" name="dates" value="${exp.dates || ""}" placeholder="2022 – Present">

      <label>Bullets (one per line)</label>
      <textarea name="bullets">${(exp.bullets || []).join("\n")}</textarea>

      <div class="button-row">
        <button type="submit" class="primary">Save Experience</button>
        <button type="button" class="secondary" data-action="delete">Delete</button>
      </div>
    </form>
  `;
}

function renderExperienceCreationForm() {
  const editor = container.querySelector("#experience-editor");
  editor.insertAdjacentHTML(
    "beforeend",
    `
    <form class="experience-form" data-experience-id="">
      <label>Company</label>
      <input type="text" name="company" placeholder="Company" required>

      <label>Title</label>
      <input type="text" name="title" placeholder="Role" required>

      <label>Dates</label>
      <input type="text" name="dates" placeholder="2024 – Present">

      <label>Bullets (one per line)</label>
      <textarea name="bullets" placeholder="Key outcomes..."></textarea>

      <div class="button-row">
        <button type="submit" class="primary">Create Experience</button>
      </div>
    </form>
  `
  );
  bindExperienceForms();
}

function bindExperienceForms() {
  container.querySelectorAll(".experience-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const formData = new FormData(form);
      const payload = {
        company: formData.get("company"),
        title: formData.get("title"),
        dates: formData.get("dates"),
        bullets: (formData.get("bullets") || "")
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean),
      };
      const id = form.dataset.experienceId;
      const isNew = !id;
      const url = isNew ? "/api/experience" : `/api/experience/${id}`;
      const method = isNew ? "POST" : "PUT";
      try {
        await apiRequest(url, {
          method,
          body: JSON.stringify(payload),
        });
        await loadExperience();
        await loadProjects(); // linked experience may change
        setStatus(`${isNew ? "Created" : "Updated"} experience "${payload.company}".`);
        renderProjectsView();
      } catch (error) {
        setStatus(error.message, true);
      }
    });

    const deleteBtn = form.querySelector('[data-action="delete"]');
    if (deleteBtn) {
      deleteBtn.addEventListener("click", async () => {
        const id = form.dataset.experienceId;
        const company = form.querySelector('input[name="company"]').value;
        if (!confirm(`Delete experience "${company}"?`)) return;
        try {
          await apiRequest(`/api/experience/${id}`, { method: "DELETE" });
          await loadExperience();
          await loadProjects();
          setStatus(`Deleted experience "${company}".`);
          renderProjectsView();
        } catch (error) {
          setStatus(error.message, true);
        }
      });
    }
  });
}

// ---------------------------------------------------------------------------
// Skills Manager
// ---------------------------------------------------------------------------
function renderSkillsView() {
  container.innerHTML = `
    <section class="pane">
      <h2>Skills Catalog</h2>
      ${Object.entries(state.skills)
        .map(
          ([category, entries]) => `
            <article class="skill-category" data-category="${category}">
              <h3>${category}</h3>
              <ul class="list">
                ${entries
                  .map(
                    (entry) => `
                      <li class="skill-item" data-skill-id="${entry.id}">
                        <div class="grid two">
                          <div>
                            <label>Label</label>
                            <input type="text" value="${entry.label}" class="skill-label-input">
                          </div>
                          <div>
                            <label>Usage</label>
                            <div>
                              ${
                                entry.usage && entry.usage.length
                                  ? entry.usage
                                      .map(
                                        (usage) =>
                                          `<span class="chip" title="${usage.project_name}">${usage.project_name}</span>`
                                      )
                                      .join("")
                                  : "<span class=\"chip\">Unused</span>"
                              }
                            </div>
                          </div>
                        </div>
                        <div class="button-row">
                          <button class="primary" data-action="save">Save</button>
                          <button class="secondary" data-action="delete">Delete</button>
                        </div>
                      </li>`
                  )
                  .join("")}
              </ul>
            </article>`
        )
        .join("")}
    </section>

    <section class="pane">
      <h2>Add a Skill</h2>
      <form id="add-skill-form">
        <label>Category</label>
        <select name="category" required>
          <option value="">Select category</option>
          ${Object.keys(state.skills)
            .map((category) => `<option value="${category}">${category}</option>`)
            .join("")}
        </select>

        <label>Label</label>
        <input type="text" name="label" placeholder="Skill label" required>

        <div class="button-row">
          <button type="submit" class="primary">Add Skill</button>
        </div>
      </form>
    </section>
  `;

  container.querySelectorAll(".skill-item").forEach((item) => {
    const category = item.closest(".skill-category").dataset.category;
    const skillId = item.dataset.skillId;
    const labelInput = item.querySelector(".skill-label-input");

    item.querySelector('[data-action="save"]').addEventListener("click", async () => {
      try {
        await apiRequest(`/api/skills/${category}/${skillId}`, {
          method: "PUT",
          body: JSON.stringify({ label: labelInput.value }),
        });
        await loadSkills();
        setStatus(`Updated skill "${labelInput.value}".`);
        renderSkillsView();
      } catch (error) {
        setStatus(error.message, true);
      }
    });

    item.querySelector('[data-action="delete"]').addEventListener("click", async () => {
      if (!confirm("Remove this skill? Projects will lose the reference.")) return;
      try {
        await apiRequest(`/api/skills/${category}/${skillId}`, { method: "DELETE" });
        await Promise.all([loadSkills(), loadProjects()]);
        setStatus("Deleted skill.");
        renderSkillsView();
      } catch (error) {
        setStatus(error.message, true);
      }
    });
  });

  const addSkillForm = container.querySelector("#add-skill-form");
  addSkillForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(addSkillForm);
    const payload = {
      category: formData.get("category"),
      label: formData.get("label"),
    };
    try {
      await apiRequest("/api/skills", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      addSkillForm.reset();
      await loadSkills();
      setStatus(`Added skill "${payload.label}".`);
      renderSkillsView();
    } catch (error) {
      setStatus(error.message, true);
    }
  });
}

// ---------------------------------------------------------------------------
// Job Config Helper
// ---------------------------------------------------------------------------
function renderJobsView() {
  container.innerHTML = `
    <section class="pane grid two">
      <div>
        <div class="button-row" style="justify-content: space-between; align-items: center;">
          <h2>Job Configs</h2>
          <button class="secondary" id="refresh-jobs-btn">Refresh</button>
        </div>
        <ul class="list" id="job-list">
          ${state.jobs
            .map(
              (job) => `
                <li>
                  <button data-job-slug="${job.slug}" class="${
                    job.slug === state.selectedJobSlug ? "active" : ""
                  }">
                    <strong>${job.title || job.slug}</strong><br>
                    <small>${job.slug}</small>
                  </button>
                </li>`
            )
            .join("")}
        </ul>
      </div>
      <div id="job-form-pane">
        ${state.selectedJobSlug && state.currentJob ? jobFormHtml(state.currentJob) : "<p>Select a job config to edit.</p>"}
      </div>
    </section>

    <section class="pane">
      <h2>Create New Job Config</h2>
      <form id="create-job-form">
        <label>Slug</label>
        <input type="text" name="slug" placeholder="acme-ml-researcher" required>

        <label>Title</label>
        <input type="text" name="title" placeholder="ML Researcher" required>

        <label>Summary Key (optional)</label>
        <select name="summary_key">
          <option value="">Use template default</option>
          ${state.summaries.map((key) => `<option value="${key}">${key}</option>`).join("")}
        </select>

        <div class="button-row">
          <button type="submit" class="primary">Create Config</button>
        </div>
      </form>
    </section>
  `;

  container.querySelectorAll("[data-job-slug]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedJobSlug = button.dataset.jobSlug;
      await loadJobDetail(state.selectedJobSlug);
      renderJobsView();
    });
  });

  const refreshBtn = container.querySelector("#refresh-jobs-btn");
  refreshBtn.addEventListener("click", async () => {
    await loadJobs();
    setStatus("Refreshed job list.");
    renderJobsView();
  });

  const createJobForm = container.querySelector("#create-job-form");
  createJobForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(createJobForm);
    const payload = {
      slug: formData.get("slug"),
      title: formData.get("title"),
    };
    const summaryKey = formData.get("summary_key");
    if (summaryKey) {
      payload.summary_key = summaryKey;
    }
    try {
      await apiRequest("/api/jobs", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await loadJobs();
      state.selectedJobSlug = payload.slug;
      await loadJobDetail(payload.slug);
      setStatus(`Created job config "${payload.slug}".`);
      renderJobsView();
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  if (state.selectedJobSlug && state.currentJob) {
    bindJobForm(state.currentJob);
  }
}

async function loadJobDetail(slug) {
  const { data } = await apiRequest(`/api/jobs/${slug}`);
  state.currentJob = data || null;
}

function jobFormHtml(job) {
  const selected = new Set(job.selected_projects || []);
  const defaultCategories = Object.keys(state.skills);
  const customOrder = Array.isArray(job.skills_order) ? job.skills_order : [];
  const categories = [
    ...customOrder.filter((category) => defaultCategories.includes(category)),
    ...defaultCategories.filter((category) => !customOrder.includes(category)),
  ];
  return `
    <form id="job-form">
      <h2>Edit Job Config</h2>

      <label>Title</label>
      <input type="text" name="title" value="${job.title || ""}">

      <label>Summary Key</label>
      <select name="summary_key">
        ${state.summaries
          .map((key) => `<option value="${key}" ${job.summary_key === key ? "selected" : ""}>${key}</option>`)
          .join("")}
      </select>

      <label>Include Freelance Experience</label>
      <select name="show_freelance">
        <option value="true" ${job.show_freelance !== false ? "selected" : ""}>Yes</option>
        <option value="false" ${job.show_freelance === false ? "selected" : ""}>No</option>
      </select>

      <label>Selected Projects</label>
      <div class="skills-checkboxes">
        ${state.projects
          .map(
            (project) => `
              <label>
                <input type="checkbox" name="selected_project" value="${project.id}" ${
              isProjectSelected(project, selected) ? "checked" : ""
            }>
                ${project.name}
              </label>`
          )
          .join("")}
      </div>

      <label>Skills Order</label>
      <div id="skills-order-list">
        ${categories
          .map(
            (category, index) => `
              <div class="button-row" data-category="${category}">
                <span>${category}</span>
                <div>
                  <button type="button" class="secondary" data-action="move-up" ${index === 0 ? "disabled" : ""}>↑</button>
                  <button type="button" class="secondary" data-action="move-down" ${
                    index === categories.length - 1 ? "disabled" : ""
                  }>↓</button>
                </div>
              </div>`
          )
          .join("")}
      </div>

      <label>Skills Labels</label>
      ${categories
        .map(
          (category) => `
            <div class="grid two" data-label-category="${category}">
              <div>
                <strong>${category}</strong>
              </div>
              <div>
                <input type="text" name="skills_label_${category}" value="${
                  job.skills_label_map?.[category] || category
                }">
              </div>
            </div>`
        )
        .join("")}

      <div class="button-row">
        <button type="submit" class="primary">Save Config</button>
        <button type="button" class="secondary" id="delete-job-btn">Delete Config</button>
      </div>
    </form>
  `;
}

function isProjectSelected(project, selectedSet) {
  if (selectedSet.has(project.id) || selectedSet.has(project.name)) return true;
  return false;
}

function bindJobForm(job) {
  const form = container.querySelector("#job-form");
  if (!form) return;

  const orderList = form.querySelector("#skills-order-list");
  const reorder = (category, direction) => {
    const categories = Array.from(orderList.querySelectorAll("[data-category]"));
    const index = categories.findIndex((node) => node.dataset.category === category);
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= categories.length) return;
    const current = categories[index];
    orderList.insertBefore(current, direction > 0 ? categories[targetIndex].nextSibling : categories[targetIndex]);
    updateMoveButtons(orderList);
  };

  const updateMoveButtons = (list) => {
    const rows = Array.from(list.querySelectorAll("[data-category]"));
    rows.forEach((row, index) => {
      const up = row.querySelector('[data-action="move-up"]');
      const down = row.querySelector('[data-action="move-down"]');
      if (up) up.disabled = index === 0;
      if (down) down.disabled = index === rows.length - 1;
    });
  };

  orderList.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const row = button.closest("[data-category]");
    const category = row.dataset.category;
    if (button.dataset.action === "move-up") {
      reorder(category, -1);
    } else if (button.dataset.action === "move-down") {
      reorder(category, +1);
    }
  });

  updateMoveButtons(orderList);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const categories = Array.from(orderList.querySelectorAll("[data-category]")).map(
      (node) => node.dataset.category
    );
    const skillsLabelMap = {};
    categories.forEach((category) => {
      const input = form.querySelector(`[name="skills_label_${category}"]`);
      skillsLabelMap[category] = input?.value || category;
    });
    const payload = {
      title: formData.get("title"),
      summary_key: formData.get("summary_key"),
      show_freelance: formData.get("show_freelance") === "true",
      selected_projects: formData.getAll("selected_project"),
      skills_order: categories,
      skills_label_map: skillsLabelMap,
    };
    try {
      await apiRequest(`/api/jobs/${job.slug}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      await loadJobs();
      await loadJobDetail(job.slug);
      setStatus(`Saved job config "${job.slug}".`);
      renderJobsView();
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  const deleteBtn = form.querySelector("#delete-job-btn");
  deleteBtn.addEventListener("click", async () => {
    if (!confirm(`Delete job config "${job.slug}"?`)) return;
    try {
      await apiRequest(`/api/jobs/${job.slug}`, { method: "DELETE" });
      state.selectedJobSlug = null;
      state.currentJob = null;
      await loadJobs();
      setStatus(`Deleted job config "${job.slug}".`);
      renderJobsView();
    } catch (error) {
      setStatus(error.message, true);
    }
  });
}

// ---------------------------------------------------------------------------
// Resume Generator
// ---------------------------------------------------------------------------
async function createResumeGeneration(jobAd) {
  const { data } = await apiRequest("/api/ai/resumes", {
    method: "POST",
    body: JSON.stringify({ job_ad: jobAd }),
  });
  return data;
}

async function deleteResumeGeneration(resumeId) {
  await apiRequest(`/api/ai/resumes/${resumeId}`, { method: "DELETE" });
}

function renderResumeView() {
  const detail = state.currentResume;
  container.innerHTML = `
    <section class="pane">
      <h2>Generate Resume & Cover Letter</h2>
      <form id="resume-form">
        <label>Job Description / Posting</label>
        <textarea name="job_ad" placeholder="Paste the job posting here..." required></textarea>
        <div class="button-row">
          <button type="submit" class="primary">Generate Package</button>
          <button type="button" class="secondary" id="refresh-resumes-btn">Refresh History</button>
        </div>
      </form>
    </section>

    <section class="pane grid two">
      <div>
        <h2>Previous Generations</h2>
        <ul class="list" id="resume-list">
          ${
            state.resumeGenerations.length
              ? state.resumeGenerations
                  .map(
                    (item) => `
              <li>
                <button data-resume-id="${item.id}" class="${item.id === state.selectedResumeId ? "active" : ""}">
                  <strong>${item.job_title || "(Untitled role)"}</strong><br>
                  <small>${formatTimestamp(item.created_at)}</small>
                </button>
              </li>`
                  )
                  .join("")
              : '<li class="empty">No generated resumes yet.</li>'
          }
        </ul>
      </div>
      <div id="resume-detail">
        ${
          detail
            ? `
          <div class="resume-detail">
            <h2>${detail.job_title || "Generated Resume"}</h2>
            <p class="meta-line">Created ${formatTimestamp(detail.created_at)}</p>
            ${
              detail.skill_labels && detail.skill_labels.length
                ? `<p><strong>Skills highlighted:</strong> ${detail.skill_labels.join(", ")}</p>`
                : ""
            }
            <form id="resume-meta-form" class="resume-meta">
              <label>Package Title</label>
              <input type="text" name="job_title" value="${escapeHtml(detail.job_title || "")}">
              <div class="button-row">
                <button type="submit" class="secondary">Save Title</button>
                <button type="button" class="secondary" id="open-resume-html-btn">Open Resume in Browser</button>
                <button type="button" class="secondary" id="open-cover-letter-btn">Open Cover Letter</button>
                <button type="button" class="secondary" id="export-pdfs-btn">Export PDFs</button>
              </div>
            </form>
            ${
              detail.resume_pdf_path || detail.cover_letter_pdf_path
                ? `<p class="hint">
                    Latest export:
                    ${
                      detail.resume_pdf_path
                        ? `<code>${detail.resume_pdf_path}</code>`
                        : "Resume PDF pending"
                    } |
                    ${
                      detail.cover_letter_pdf_path
                        ? `<code>${detail.cover_letter_pdf_path}</code>`
                        : "Cover letter PDF pending"
                    }
                  </p>`
                : ""
            }
            <p>${escapeHtml(detail.summary || "")}</p>
            <div class="button-row">
              <button type="button" class="secondary" id="delete-resume-btn">Delete</button>
            </div>
            <h3>Resume Preview</h3>
            <iframe id="resume-preview" class="resume-preview"></iframe>
            <details class="resume-html-editor">
              <summary>Edit Resume HTML</summary>
              <form id="resume-html-form">
                <label>Resume HTML</label>
                <textarea name="resume_html" class="code-block" spellcheck="false">${escapeHtml(
                  detail.resume_html || ""
                )}</textarea>
                <div class="button-row">
                  <button type="submit" class="secondary">Save Resume HTML</button>
                </div>
              </form>
            </details>
            <h3>Cover Letter</h3>
            <form id="cover-letter-form">
              <label>Cover Letter Text</label>
              <textarea name="cover_letter_text">${escapeHtml(detail.cover_letter || "")}</textarea>
              <label>AI Guidance (optional)</label>
              <textarea name="instructions" placeholder="Focus on honesty, reference specific projects, etc."></textarea>
              <div class="button-row">
                <button type="submit" class="primary" data-action="save">Save Cover Letter</button>
                <button type="submit" class="secondary" data-action="generate">${
                  detail.cover_letter ? "Regenerate with AI" : "Generate with AI"
                }</button>
              </div>
            </form>
          </div>`
            : "<p>Select a generated resume to preview.</p>"
        }
      </div>
    </section>
  `;

  const form = container.querySelector("#resume-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const jobAd = formData.get("job_ad");
    if (!jobAd) {
      setStatus("Provide a job description to generate a resume.", true);
      return;
    }
    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    setStatus("Generating resume package...");
    try {
      const record = await createResumeGeneration(jobAd);
      await loadResumeGenerations();
      state.selectedResumeId = record.id;
      state.currentResume = record;
      setStatus(
        `Created resume for ${record.job_title || record.id}. Generate a cover letter when you're ready.`
      );
      renderResumeView();
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      submitBtn.disabled = false;
    }
  });

  const refreshBtn = container.querySelector("#refresh-resumes-btn");
  refreshBtn.addEventListener("click", async () => {
    try {
      await loadResumeGenerations();
      setStatus("Refreshed generated resume list.");
      renderResumeView();
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  container.querySelectorAll("[data-resume-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedResumeId = button.dataset.resumeId;
      try {
        await loadResumeDetail(state.selectedResumeId);
        renderResumeView();
      } catch (error) {
        setStatus(error.message, true);
      }
    });
  });

  const deleteBtn = container.querySelector("#delete-resume-btn");
  if (deleteBtn && detail) {
    deleteBtn.addEventListener("click", async () => {
      if (!confirm("Delete this generated resume package?")) return;
      try {
        await deleteResumeGeneration(detail.id);
        await loadResumeGenerations();
        state.currentResume = null;
        state.selectedResumeId = null;
        setStatus("Deleted generated resume.");
        renderResumeView();
      } catch (error) {
        setStatus(error.message, true);
      }
    });
  }

  const metaForm = container.querySelector("#resume-meta-form");
  if (metaForm && detail) {
    metaForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const formData = new FormData(metaForm);
      const jobTitle = formData.get("job_title") || "";
      const submitBtn = metaForm.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      setStatus("Saving title...");
      try {
        const updated = await saveResumeMetadata(detail.id, { job_title: jobTitle });
        state.currentResume = updated;
        await loadResumeGenerations();
        setStatus("Title saved.");
        renderResumeView();
      } catch (error) {
        setStatus(error.message, true);
      } finally {
        submitBtn.disabled = false;
      }
    });

    const resumeUrl = `/api/ai/resumes/${detail.id}/resume-html`;
    const coverUrl = `/api/ai/resumes/${detail.id}/cover-letter-txt`;

    const openResumeBtn = metaForm.querySelector("#open-resume-html-btn");
    if (openResumeBtn) {
      openResumeBtn.addEventListener("click", () => {
        window.open(resumeUrl, "_blank", "noopener");
      });
    }

    const openCoverBtn = metaForm.querySelector("#open-cover-letter-btn");
    if (openCoverBtn) {
      openCoverBtn.addEventListener("click", () => {
        window.open(coverUrl, "_blank", "noopener");
      });
    }

    const exportBtn = metaForm.querySelector("#export-pdfs-btn");
    if (exportBtn) {
      exportBtn.addEventListener("click", async () => {
        exportBtn.disabled = true;
        setStatus("Exporting PDFs...");
        try {
          const updated = await exportResumePdfs(detail.id);
          state.currentResume = updated;
          await loadResumeGenerations();
          setStatus("Exported PDFs.");
          renderResumeView();
        } catch (error) {
          setStatus(error.message, true);
        } finally {
          exportBtn.disabled = false;
        }
      });
    }
  }

  const resumeHtmlForm = container.querySelector("#resume-html-form");
  if (resumeHtmlForm && detail) {
    resumeHtmlForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const formData = new FormData(resumeHtmlForm);
      const resumeHtml = formData.get("resume_html") || "";
      const submitBtn = resumeHtmlForm.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      setStatus("Saving resume HTML...");
      try {
        const updated = await saveResumeHtml(detail.id, resumeHtml);
        state.currentResume = updated;
        await loadResumeGenerations();
        setStatus("Resume HTML saved.");
        renderResumeView();
      } catch (error) {
        setStatus(error.message, true);
      } finally {
        submitBtn.disabled = false;
      }
    });
  }

  const coverForm = container.querySelector("#cover-letter-form");
  if (coverForm && detail) {
    coverForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submitBtn = event.submitter || coverForm.querySelector('button[type="submit"]');
      if (!submitBtn) return;
      const action = submitBtn.dataset.action || "save";
      const formData = new FormData(coverForm);
      const coverLetterText = formData.get("cover_letter_text") || "";
      const instructions = formData.get("instructions") || "";
      submitBtn.disabled = true;
      setStatus(action === "save" ? "Saving cover letter..." : "Generating cover letter...");
      try {
        const updated =
          action === "save"
            ? await requestCoverLetter(detail.id, { coverLetter: coverLetterText })
            : await requestCoverLetter(detail.id, { instructions });
        state.currentResume = updated;
        await loadResumeGenerations();
        setStatus(action === "save" ? "Cover letter saved." : "Cover letter ready.");
        renderResumeView();
      } catch (error) {
        setStatus(error.message, true);
      } finally {
        submitBtn.disabled = false;
      }
    });
  }

  const iframe = container.querySelector("#resume-preview");
  if (iframe && detail) {
    const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
    if (iframeDoc) {
      iframeDoc.open();
      iframeDoc.write(detail.resume_html || "<p>Resume HTML not available.</p>");
      iframeDoc.close();
    } else {
      iframe.srcdoc = detail.resume_html || "<p>Resume HTML not available.</p>";
    }
  }
}

function renderSettingsView() {
  const prompts = state.prompts || {};
  container.innerHTML = `
    <section class="pane">
      <h2>Prompt Settings</h2>
      <form id="prompt-form" class="grid">
        <div>
          <label>Project Generation Guidance</label>
          <textarea name="project_extra_instruction" placeholder="Extra system instructions for project drafting...">${escapeHtml(
            prompts.project_extra_instruction || ""
          )}</textarea>
        </div>
        <div>
          <label>Resume Generation Guidance</label>
          <textarea name="resume_extra_instruction" placeholder="Extra system instructions for resume drafting...">${escapeHtml(
            prompts.resume_extra_instruction || ""
          )}</textarea>
        </div>
        <div>
          <label>Cover Letter Guidance</label>
          <textarea name="cover_letter_extra_instruction" placeholder="Extra system instructions for cover letters...">${escapeHtml(
            prompts.cover_letter_extra_instruction || ""
          )}</textarea>
        </div>
        <div class="button-row">
          <button type="submit" class="primary">Save Prompts</button>
        </div>
      </form>
      <p class="hint">
        These instructions are appended to the system prompts before each AI call. Use them to reinforce tone, honesty, or other preferences. You can still pass extra guidance per cover letter when generating one.
      </p>
    </section>
  `;

  const form = container.querySelector("#prompt-form");
  if (form) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const formData = new FormData(form);
      const updates = {
        project_extra_instruction: formData.get("project_extra_instruction") || "",
        resume_extra_instruction: formData.get("resume_extra_instruction") || "",
        cover_letter_extra_instruction: formData.get("cover_letter_extra_instruction") || "",
      };
      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      setStatus("Saving prompt settings...");
      try {
        await savePrompts(updates);
        setStatus("Prompt settings saved.");
      } catch (error) {
        setStatus(error.message, true);
      } finally {
        submitBtn.disabled = false;
      }
    });
  }
}

init();

function formatTimestamp(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function escapeHtml(text) {
  if (text == null) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}