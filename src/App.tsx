import React, { useState, useMemo, useEffect } from 'react';
import {
  Briefcase,
  Search,
  MapPin,
  Building2,
  DollarSign,
  Bookmark,
  ExternalLink,
  Filter,
  CheckCircle2,
  Sparkles,
  Layers,
  GraduationCap,
  Globe2,
  X,
  Share2,
  ShieldCheck,
  TrendingUp,
  User,
  Heart
} from 'lucide-react';
import initialData from './data/initialData.json';

interface Job {
  id: number;
  title: string;
  slug: string;
  company_id: number;
  company_name: string;
  company_logo: string;
  company_website?: string;
  category_id: number;
  category_name: string;
  description: string;
  requirements?: string;
  benefits?: string;
  skills_required?: string;
  job_type: string;
  experience_level: string;
  work_mode: string;
  location: string;
  salary_min: number;
  salary_max: number;
  salary_currency: string;
  original_url: string;
  is_featured: number;
  is_remote: number;
  is_fresher: number;
  is_internship: number;
  views_count?: number;
  application_count?: number;
  created_at: string;
}

interface Company {
  id: number;
  name: string;
  slug: string;
  logo_url: string;
  website: string;
  industry: string;
  location: string;
  description?: string;
  job_count: number;
}

interface Category {
  id: number;
  name: string;
  slug: string;
  icon?: string;
  job_count?: number;
}

export default function App() {
  const [searchTerm, setSearchTerm] = useState('');
  const [locationTerm, setLocationTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [selectedMode, setSelectedMode] = useState<string>('all');
  const [selectedLevel, setSelectedLevel] = useState<string>('all');
  const [activeTab, setActiveTab] = useState<'all' | 'internships' | 'fresher' | 'remote' | 'companies' | 'saved'>('all');
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  
  // LocalStorage saved jobs state
  const [savedJobIds, setSavedJobIds] = useState<number[]>(() => {
    try {
      const stored = localStorage.getItem('jp_saved_jobs');
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  // Track applied jobs
  const [appliedJobIds, setAppliedJobIds] = useState<number[]>(() => {
    try {
      const stored = localStorage.getItem('jp_applied_jobs');
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const toggleSaveJob = (e: React.MouseEvent, jobId: number) => {
    e.stopPropagation();
    setSavedJobIds((prev) => {
      let next: number[];
      if (prev.includes(jobId)) {
        next = prev.filter((id) => id !== jobId);
        showToast('Job removed from bookmarks');
      } else {
        next = [...prev, jobId];
        showToast('Job saved to bookmarks!');
      }
      localStorage.setItem('jp_saved_jobs', JSON.stringify(next));
      return next;
    });
  };

  const trackApplication = (jobId: number) => {
    if (!appliedJobIds.includes(jobId)) {
      const updated = [...appliedJobIds, jobId];
      setAppliedJobIds(updated);
      localStorage.setItem('jp_applied_jobs', JSON.stringify(updated));
    }
    showToast('Application tracked in your profile!');
  };

  const jobs: Job[] = initialData.jobs as Job[];
  const companies: Company[] = initialData.companies as Company[];
  const categories: Category[] = initialData.categories as Category[];

  // Filtered jobs calculation
  const filteredJobs = useMemo(() => {
    return jobs.filter((job) => {
      // Tab filter
      if (activeTab === 'internships' && !job.is_internship && job.job_type !== 'Internship') return false;
      if (activeTab === 'fresher' && !job.is_fresher && job.experience_level !== 'Fresher') return false;
      if (activeTab === 'remote' && !job.is_remote && job.work_mode !== 'Remote') return false;
      if (activeTab === 'saved' && !savedJobIds.includes(job.id)) return false;

      // Category filter
      if (selectedCategory !== 'all' && String(job.category_id) !== selectedCategory) return false;

      // Type filter
      if (selectedType !== 'all' && job.job_type !== selectedType) return false;

      // Mode filter
      if (selectedMode !== 'all' && job.work_mode !== selectedMode) return false;

      // Level filter
      if (selectedLevel !== 'all' && job.experience_level !== selectedLevel) return false;

      // Search term
      if (searchTerm.trim()) {
        const query = searchTerm.toLowerCase();
        const matchTitle = job.title.toLowerCase().includes(query);
        const matchCompany = job.company_name.toLowerCase().includes(query);
        const matchSkills = (job.skills_required || '').toLowerCase().includes(query);
        const matchDesc = job.description.toLowerCase().includes(query);
        if (!matchTitle && !matchCompany && !matchSkills && !matchDesc) return false;
      }

      // Location filter
      if (locationTerm.trim()) {
        const loc = locationTerm.toLowerCase();
        if (!job.location.toLowerCase().includes(loc)) return false;
      }

      return true;
    });
  }, [jobs, activeTab, selectedCategory, selectedType, selectedMode, selectedLevel, searchTerm, locationTerm, savedJobIds]);

  const formatSalary = (min: number, max: number) => {
    if (min && max) {
      return `$${min.toLocaleString()} - $${max.toLocaleString()}`;
    }
    if (min) return `$${min.toLocaleString()}+`;
    return 'Competitive';
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 font-sans flex flex-col">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-slate-900 text-white px-5 py-3 rounded-xl shadow-2xl flex items-center gap-3 border border-slate-700 animate-bounce">
          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          <span className="text-sm font-medium">{toastMessage}</span>
        </div>
      )}

      {/* Top Banner / Header */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 text-white flex items-center justify-center font-black text-xl shadow-md shadow-indigo-200">
              J
            </div>
            <div>
              <span className="font-extrabold text-slate-900 tracking-tight text-lg sm:text-xl">
                JOBPOST <span className="text-indigo-600">AGGREGATOR</span>
              </span>
              <span className="hidden sm:inline-block ml-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Search • Discover • Apply
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="flex items-center gap-1 sm:gap-2">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-3 py-1.5 rounded-lg text-sm font-semibold transition ${
                activeTab === 'all'
                  ? 'bg-indigo-50 text-indigo-700'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              Jobs
            </button>
            <button
              onClick={() => setActiveTab('internships')}
              className={`px-3 py-1.5 rounded-lg text-sm font-semibold transition flex items-center gap-1.5 ${
                activeTab === 'internships'
                  ? 'bg-indigo-50 text-indigo-700'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <GraduationCap className="w-4 h-4 text-emerald-600" />
              <span>Internships</span>
            </button>
            <button
              onClick={() => setActiveTab('remote')}
              className={`px-3 py-1.5 rounded-lg text-sm font-semibold transition flex items-center gap-1.5 ${
                activeTab === 'remote'
                  ? 'bg-indigo-50 text-indigo-700'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <Globe2 className="w-4 h-4 text-sky-600" />
              <span>Remote</span>
            </button>
            <button
              onClick={() => setActiveTab('companies')}
              className={`px-3 py-1.5 rounded-lg text-sm font-semibold transition ${
                activeTab === 'companies'
                  ? 'bg-indigo-50 text-indigo-700'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              Companies
            </button>
            <button
              onClick={() => setActiveTab('saved')}
              className={`px-3 py-1.5 rounded-lg text-sm font-semibold transition flex items-center gap-1.5 ${
                activeTab === 'saved'
                  ? 'bg-amber-50 text-amber-700'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <Bookmark className={`w-4 h-4 ${savedJobIds.length > 0 ? 'text-amber-500 fill-amber-500' : ''}`} />
              <span>Saved ({savedJobIds.length})</span>
            </button>
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <section className="bg-gradient-to-b from-indigo-50/70 via-white to-slate-50 pt-12 pb-10 border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 text-center">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-100/80 text-indigo-700 text-xs font-bold uppercase tracking-wider mb-4 border border-indigo-200">
            <Sparkles className="w-3.5 h-3.5" />
            Aggregated from Verified Multi-Source Career Portals
          </div>
          <h1 className="text-3xl sm:text-5xl font-black text-slate-900 tracking-tight leading-tight mb-4">
            Find Your Dream Career Opportunity
          </h1>
          <p className="text-base sm:text-lg text-slate-600 max-w-2xl mx-auto mb-8">
            Centralized job post aggregation tracking internships, freshers, tech engineering, and high-impact remote careers.
          </p>

          {/* Search Box */}
          <div className="bg-white p-2.5 sm:p-3 rounded-2xl shadow-xl shadow-indigo-100/60 border border-slate-200 flex flex-col md:flex-row items-center gap-2 max-w-4xl mx-auto">
            <div className="flex items-center gap-2.5 w-full md:flex-1 px-3 py-2 border-b md:border-b-0 md:border-r border-slate-100">
              <Search className="w-5 h-5 text-indigo-500 shrink-0" />
              <input
                type="text"
                placeholder="Job title, keywords, or company..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full text-sm text-slate-800 placeholder-slate-400 bg-transparent focus:outline-none"
              />
            </div>

            <div className="flex items-center gap-2.5 w-full md:w-64 px-3 py-2 border-b md:border-b-0 md:border-r border-slate-100">
              <MapPin className="w-5 h-5 text-emerald-500 shrink-0" />
              <input
                type="text"
                placeholder="City, State, or Remote..."
                value={locationTerm}
                onChange={(e) => setLocationTerm(e.target.value)}
                className="w-full text-sm text-slate-800 placeholder-slate-400 bg-transparent focus:outline-none"
              />
            </div>

            <button
              onClick={() => setActiveTab('all')}
              className="w-full md:w-auto px-6 py-3 bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white font-bold text-sm rounded-xl transition shadow-md shadow-indigo-300"
            >
              Search Jobs
            </button>
          </div>

          {/* Live Platform Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-10 max-w-3xl mx-auto">
            <div className="bg-white/80 backdrop-blur p-3.5 rounded-xl border border-slate-200/80 shadow-sm">
              <div className="text-2xl font-black text-indigo-600">{jobs.length}</div>
              <div className="text-xs font-semibold text-slate-500 uppercase">Active Postings</div>
            </div>
            <div className="bg-white/80 backdrop-blur p-3.5 rounded-xl border border-slate-200/80 shadow-sm">
              <div className="text-2xl font-black text-emerald-600">{companies.length}</div>
              <div className="text-xs font-semibold text-slate-500 uppercase">Top Employers</div>
            </div>
            <div className="bg-white/80 backdrop-blur p-3.5 rounded-xl border border-slate-200/80 shadow-sm">
              <div className="text-2xl font-black text-violet-600">{categories.length}</div>
              <div className="text-xs font-semibold text-slate-500 uppercase">Disciplines</div>
            </div>
            <div className="bg-white/80 backdrop-blur p-3.5 rounded-xl border border-slate-200/80 shadow-sm">
              <div className="text-2xl font-black text-amber-600">100%</div>
              <div className="text-xs font-semibold text-slate-500 uppercase">Verified Sources</div>
            </div>
          </div>
        </div>
      </section>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full">
        {/* If Companies Tab is selected */}
        {activeTab === 'companies' ? (
          <div>
            <div className="mb-6">
              <h2 className="text-2xl font-black text-slate-900 tracking-tight">Verified Hiring Companies</h2>
              <p className="text-sm text-slate-500">Explore trusted organizations currently recruiting top talent.</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {companies.map((comp) => (
                <div key={comp.id} className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm hover:shadow-md transition">
                  <div className="flex items-center gap-4 mb-4">
                    <img
                      src={comp.logo_url}
                      alt={comp.name}
                      className="w-14 h-14 rounded-xl object-cover border border-slate-100 shadow-sm"
                      onError={(e) => {
                        (e.target as HTMLElement).style.display = 'none';
                      }}
                    />
                    <div>
                      <h3 className="font-bold text-slate-900 text-lg">{comp.name}</h3>
                      <span className="text-xs font-semibold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-md">
                        {comp.industry}
                      </span>
                    </div>
                  </div>
                  <p className="text-xs text-slate-600 line-clamp-3 mb-4">{comp.description}</p>
                  <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                    <span className="text-xs font-semibold text-slate-500 flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5" />
                      {comp.location}
                    </span>
                    <button
                      onClick={() => {
                        setSearchTerm(comp.name);
                        setActiveTab('all');
                      }}
                      className="text-xs font-bold text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
                    >
                      View {comp.job_count} Jobs →
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col lg:flex-row gap-8">
            {/* Sidebar Filters */}
            <aside className="w-full lg:w-64 shrink-0 space-y-6">
              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-5">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                  <h3 className="font-bold text-slate-900 flex items-center gap-2 text-sm">
                    <Filter className="w-4 h-4 text-indigo-600" />
                    Filters
                  </h3>
                  {(selectedCategory !== 'all' || selectedType !== 'all' || selectedMode !== 'all' || selectedLevel !== 'all') && (
                    <button
                      onClick={() => {
                        setSelectedCategory('all');
                        setSelectedType('all');
                        setSelectedMode('all');
                        setSelectedLevel('all');
                      }}
                      className="text-xs font-bold text-indigo-600 hover:underline"
                    >
                      Reset All
                    </button>
                  )}
                </div>

                {/* Category Filter */}
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Category</label>
                  <select
                    value={selectedCategory}
                    onChange={(e) => setSelectedCategory(e.target.value)}
                    className="w-full p-2.5 rounded-xl border border-slate-200 text-xs font-semibold text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="all">All Disciplines</option>
                    {categories.map((cat) => (
                      <option key={cat.id} value={cat.id}>
                        {cat.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Job Type Filter */}
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Job Type</label>
                  <select
                    value={selectedType}
                    onChange={(e) => setSelectedType(e.target.value)}
                    className="w-full p-2.5 rounded-xl border border-slate-200 text-xs font-semibold text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="all">Any Work Arrangement</option>
                    <option value="Full-time">Full-time</option>
                    <option value="Internship">Internship</option>
                    <option value="Contract">Contract</option>
                  </select>
                </div>

                {/* Work Mode */}
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Work Mode</label>
                  <select
                    value={selectedMode}
                    onChange={(e) => setSelectedMode(e.target.value)}
                    className="w-full p-2.5 rounded-xl border border-slate-200 text-xs font-semibold text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="all">Any Location Mode</option>
                    <option value="Remote">Remote</option>
                    <option value="Hybrid">Hybrid</option>
                    <option value="On-site">On-site</option>
                  </select>
                </div>

                {/* Experience Level */}
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Experience</label>
                  <select
                    value={selectedLevel}
                    onChange={(e) => setSelectedLevel(e.target.value)}
                    className="w-full p-2.5 rounded-xl border border-slate-200 text-xs font-semibold text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="all">All Experience Levels</option>
                    <option value="Fresher">Fresher / Entry-Level</option>
                    <option value="1-3 years">1-3 years</option>
                    <option value="3-5 years">3-5 years</option>
                    <option value="5+ years">5+ years</option>
                  </select>
                </div>
              </div>
            </aside>

            {/* Job Listings List */}
            <div className="flex-1">
              <div className="flex items-center justify-between mb-4">
                <span className="text-sm font-bold text-slate-700">
                  Showing <span className="text-indigo-600">{filteredJobs.length}</span> positions
                </span>
                {activeTab === 'saved' && (
                  <span className="text-xs font-semibold bg-amber-100 text-amber-800 px-2.5 py-1 rounded-full">
                    Bookmarked Jobs
                  </span>
                )}
              </div>

              {filteredJobs.length === 0 ? (
                <div className="bg-white rounded-2xl p-12 text-center border border-slate-200">
                  <Briefcase className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                  <h3 className="font-bold text-slate-800 text-base mb-1">No matching jobs found</h3>
                  <p className="text-xs text-slate-500 mb-4">Try clearing filters or search terms.</p>
                  <button
                    onClick={() => {
                      setSearchTerm('');
                      setLocationTerm('');
                      setSelectedCategory('all');
                      setSelectedType('all');
                      setSelectedMode('all');
                      setSelectedLevel('all');
                      setActiveTab('all');
                    }}
                    className="px-4 py-2 bg-indigo-50 text-indigo-700 font-bold text-xs rounded-lg hover:bg-indigo-100"
                  >
                    Clear All Filters
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  {filteredJobs.map((job) => {
                    const isSaved = savedJobIds.includes(job.id);
                    const isApplied = appliedJobIds.includes(job.id);

                    return (
                      <div
                        key={job.id}
                        onClick={() => setSelectedJob(job)}
                        className="bg-white p-5 rounded-2xl border border-slate-200 hover:border-indigo-300 shadow-sm hover:shadow-md transition cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-4 group"
                      >
                        <div className="flex items-start gap-4">
                          <img
                            src={job.company_logo}
                            alt={job.company_name}
                            className="w-12 h-12 rounded-xl object-cover border border-slate-100 shrink-0"
                            onError={(e) => {
                              (e.target as HTMLElement).style.display = 'none';
                            }}
                          />
                          <div>
                            <div className="flex items-center gap-2 flex-wrap mb-1">
                              <h3 className="font-extrabold text-slate-900 group-hover:text-indigo-600 transition text-base">
                                {job.title}
                              </h3>
                              {job.is_featured === 1 && (
                                <span className="bg-amber-100 text-amber-800 text-[10px] font-black uppercase px-2 py-0.5 rounded-full">
                                  Featured
                                </span>
                              )}
                              {isApplied && (
                                <span className="bg-emerald-100 text-emerald-800 text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                                  <CheckCircle2 className="w-3 h-3" /> Applied
                                </span>
                              )}
                            </div>
                            <div className="text-xs text-slate-500 font-semibold mb-2">
                              {job.company_name} • <span className="text-slate-600">{job.category_name}</span>
                            </div>

                            {/* Tags */}
                            <div className="flex items-center gap-2 flex-wrap text-xs text-slate-600">
                              <span className="bg-slate-100 px-2 py-0.5 rounded-md font-medium flex items-center gap-1">
                                <MapPin className="w-3 h-3 text-slate-400" />
                                {job.location}
                              </span>
                              <span className="bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-md font-semibold">
                                {job.work_mode}
                              </span>
                              <span className="bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-md font-semibold">
                                {job.job_type}
                              </span>
                              <span className="font-bold text-slate-900">
                                {formatSalary(job.salary_min, job.salary_max)}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-2 sm:shrink-0 self-end sm:self-center">
                          <button
                            onClick={(e) => toggleSaveJob(e, job.id)}
                            className={`p-2.5 rounded-xl border transition ${
                              isSaved
                                ? 'bg-amber-50 border-amber-200 text-amber-600'
                                : 'border-slate-200 text-slate-400 hover:text-slate-700 hover:bg-slate-50'
                            }`}
                            title={isSaved ? 'Remove Bookmark' : 'Save Job'}
                          >
                            <Bookmark className={`w-4 h-4 ${isSaved ? 'fill-amber-500' : ''}`} />
                          </button>
                          <button
                            onClick={() => setSelectedJob(job)}
                            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow-sm transition"
                          >
                            View Details
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Detail Modal */}
      {selectedJob && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl border border-slate-100 flex flex-col">
            {/* Modal Header */}
            <div className="p-6 border-b border-slate-100 flex items-start justify-between gap-4 sticky top-0 bg-white z-10">
              <div className="flex items-center gap-4">
                <img
                  src={selectedJob.company_logo}
                  alt={selectedJob.company_name}
                  className="w-14 h-14 rounded-2xl object-cover border border-slate-100 shadow-sm"
                />
                <div>
                  <h2 className="text-xl font-black text-slate-900">{selectedJob.title}</h2>
                  <div className="text-sm font-semibold text-slate-500">
                    {selectedJob.company_name} • {selectedJob.location}
                  </div>
                </div>
              </div>
              <button
                onClick={() => setSelectedJob(null)}
                className="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-6 flex-1">
              {/* Badges bar */}
              <div className="flex flex-wrap gap-2 text-xs font-bold">
                <span className="bg-indigo-50 text-indigo-700 px-3 py-1.5 rounded-lg">
                  {selectedJob.job_type}
                </span>
                <span className="bg-emerald-50 text-emerald-700 px-3 py-1.5 rounded-lg">
                  {selectedJob.work_mode}
                </span>
                <span className="bg-violet-50 text-violet-700 px-3 py-1.5 rounded-lg">
                  {selectedJob.experience_level}
                </span>
                <span className="bg-amber-50 text-amber-800 px-3 py-1.5 rounded-lg font-black">
                  {formatSalary(selectedJob.salary_min, selectedJob.salary_max)}
                </span>
              </div>

              {/* Description */}
              <div>
                <h4 className="text-xs font-black uppercase text-slate-400 tracking-wider mb-2">Job Overview</h4>
                <p className="text-sm text-slate-700 leading-relaxed">{selectedJob.description}</p>
              </div>

              {/* Requirements */}
              {selectedJob.requirements && (
                <div>
                  <h4 className="text-xs font-black uppercase text-slate-400 tracking-wider mb-2">Key Requirements</h4>
                  <p className="text-sm text-slate-700 leading-relaxed">{selectedJob.requirements}</p>
                </div>
              )}

              {/* Benefits */}
              {selectedJob.benefits && (
                <div>
                  <h4 className="text-xs font-black uppercase text-slate-400 tracking-wider mb-2">Perks & Benefits</h4>
                  <p className="text-sm text-slate-700 leading-relaxed">{selectedJob.benefits}</p>
                </div>
              )}

              {/* Required Skills */}
              {selectedJob.skills_required && (
                <div>
                  <h4 className="text-xs font-black uppercase text-slate-400 tracking-wider mb-2">Required Skills</h4>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedJob.skills_required.split(',').map((skill, idx) => (
                      <span key={idx} className="bg-slate-100 text-slate-800 text-xs font-semibold px-2.5 py-1 rounded-md">
                        {skill.trim()}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-6 border-t border-slate-100 flex items-center justify-between gap-3 bg-slate-50 rounded-b-3xl">
              <button
                onClick={(e) => toggleSaveJob(e, selectedJob.id)}
                className="px-4 py-2.5 rounded-xl border border-slate-200 bg-white font-bold text-xs text-slate-700 hover:bg-slate-100 flex items-center gap-2"
              >
                <Bookmark className={`w-4 h-4 ${savedJobIds.includes(selectedJob.id) ? 'fill-amber-500 text-amber-500' : ''}`} />
                {savedJobIds.includes(selectedJob.id) ? 'Saved' : 'Save Job'}
              </button>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => trackApplication(selectedJob.id)}
                  className={`px-4 py-2.5 rounded-xl font-bold text-xs border transition ${
                    appliedJobIds.includes(selectedJob.id)
                      ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
                      : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  {appliedJobIds.includes(selectedJob.id) ? '✓ Tracked Applied' : 'Track Application'}
                </button>
                <a
                  href={selectedJob.original_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow-md flex items-center gap-1.5 transition"
                >
                  <span>Apply on Official Portal</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-6 mt-12 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div>
            © 2026 <strong>JobPost Aggregator</strong> — Centralized Career Discovery.
          </div>
          <div className="flex items-center gap-4 font-semibold text-slate-600">
            <span>Powered by Node.js & React</span>
            <span>•</span>
            <span>Verified Sources</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
