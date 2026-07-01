import { useState, useMemo, useEffect } from "react";
import axios from "../../lib/axios";
import { NDCRecord } from "../../types";
import { exportToExcel } from "../../utils/excelExport";
import { PPTDownloadButton } from "../../components/common/PPTDownloadButton";
import { FullScreenModal } from "../../components/common/FullScreenModal";
import { LoadingScreen } from "../../components/common/LoadingScreen";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../../components/ui/dialog";
import { FileText, Download, Filter, CheckCircle, XCircle, Clock, Send, CheckSquare, Mail, TrendingUp, ChevronLeft, ChevronRight } from "lucide-react";
import { toast } from "sonner";

export function FNFManagement() {
  const [mockNDCData, setMockNDCData] = useState<NDCRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = () => {
    axios.get("/api/v1/fnf-records").then((res) => {
      const data = res.data?.data || res.data;
      setMockNDCData(Array.isArray(data) ? data : []);
      setIsLoading(false);
    });
  };


  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedRecord, setSelectedRecord] = useState<NDCRecord | null>(null);
  const [actionDialogOpen, setActionDialogOpen] = useState(false);
  const [kpiModalOpen, setKpiModalOpen] = useState(false);
  const [kpiModalData, setKpiModalData] = useState<{ title: string; data: NDCRecord[] }>({ title: "", data: [] });
  const [mailDialogOpen, setMailDialogOpen] = useState(false);
  const [mailRecord, setMailRecord] = useState<NDCRecord | null>(null);
  const [mailEmailTo, setMailEmailTo] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [kpiCurrentPage, setKpiCurrentPage] = useState(1);

  // F&F eligible = NDC Completed AND GCC HR Completed
  const isEligible = (r: NDCRecord) =>
    r.ndcStage === "NDC Completed" && r.gccHrApprovalStatus === "Completed";

  const eligibleRecords = useMemo(() => mockNDCData.filter(isEligible), [mockNDCData]);

  const filteredData = useMemo(() => {
    let filtered = eligibleRecords;
    if (statusFilter) {
      if (statusFilter === "Done") filtered = filtered.filter((r) => r.isFnfCompleted);
      else if (statusFilter === "Closed") filtered = filtered.filter((r) => r.isFnfClosed);
      else if (statusFilter === "Open") filtered = filtered.filter((r) => !r.isFnfCompleted && !r.isFnfRevision);
      else if (statusFilter === "Revision Required") filtered = filtered.filter((r) => r.isFnfRevision);
    } else {
      // By default (All statuses), exclude closed records from the list
      filtered = filtered.filter((r) => !r.isFnfClosed);
    }
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (r) => r.employeeName.toLowerCase().includes(query) || r.personNumber.toLowerCase().includes(query)
      );
    }
    return filtered;
  }, [eligibleRecords, statusFilter, searchQuery]);

  const itemsPerPage = 10;
  const totalPages = Math.max(1, Math.ceil(filteredData.length / itemsPerPage));
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedData = filteredData.slice(startIndex, startIndex + itemsPerPage);

  const kpiTotalPages = Math.max(1, Math.ceil(kpiModalData.data.length / itemsPerPage));
  const kpiStartIndex = (kpiCurrentPage - 1) * itemsPerPage;
  const kpiPaginatedData = kpiModalData.data.slice(kpiStartIndex, kpiStartIndex + itemsPerPage);

  const fnfStats = useMemo(() => {
    const total = eligibleRecords.filter((r) => !r.isFnfClosed).length;
    const done = eligibleRecords.filter((r) => r.isFnfCompleted).length;
    const open = eligibleRecords.filter((r) => !r.isFnfCompleted && !r.isFnfRevision).length;
    const revision = eligibleRecords.filter((r) => r.isFnfRevision).length;
    const closed = eligibleRecords.filter((r) => r.isFnfClosed).length;

    // F&F TAT = fnfCompletedDate - gccInitiateDate
    const tatRecords = eligibleRecords.filter((r) => r.isFnfCompleted && r.fnfCompletedDate && r.gccInitiateDate);
    const avgTAT = tatRecords.length > 0
      ? Math.round(
          tatRecords.reduce((sum, r) => {
            const end = new Date(r.fnfCompletedDate);
            const start = new Date(r.gccInitiateDate);
            return sum + Math.abs((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
          }, 0) / tatRecords.length
        )
      : 0;

    return { total, done, open, revision, closed, avgTAT };
  }, [eligibleRecords]);

  const handleAction = (record: NDCRecord, action: "closed" | "revision") => {
    if (action === "closed") {
      // Mark as F&F Closed (which automatically completes it too)
      axios.put(`/api/v1/ndc-records/${record.id}`, {
        is_fnf_closed: true,
        is_fnf_completed: true,
        fnf_document_count: 1,
      }).then(() => {
        fetchData();
        toast.success(`F&F marked as Closed and Completed for ${record.employeeName} (${record.personNumber})`);
      });
    } else {
      // Mark as Revision Required (multiple docs)
      axios.put(`/api/v1/ndc-records/${record.id}`, {
        is_fnf_revision: true,
        is_fnf_closed: false,
        is_fnf_completed: false,
        fnf_document_count: 2,
      }).then(() => {
        fetchData();
        toast.success(`F&F marked as Revision Required for ${record.employeeName} (${record.personNumber})`);
      });
    }
    setActionDialogOpen(false);
    setSelectedRecord(null);
  };

  const handleDocumentView = (record: NDCRecord) => {
    if (record.fnfDocument) {
      window.open(`/api/v1/download-document/${record.fnfDocument}`, "_blank");
    } else {
      toast.error("No document available for this employee");
    }
  };

  const handleKPIClick = (type: "total" | "done" | "open" | "revision" | "closed" | "avgTAT") => {
    const map = {
      total: { title: "Total F&F In Process", data: eligibleRecords.filter((r) => !r.isFnfClosed) },
      done: { title: "F&F Completed", data: eligibleRecords.filter((r) => r.isFnfCompleted) },
      open: { title: "F&F Open", data: eligibleRecords.filter((r) => !r.isFnfCompleted && !r.isFnfRevision) },
      revision: { title: "Revision Required", data: eligibleRecords.filter((r) => r.isFnfRevision) },
      closed: { title: "F&F Closed", data: eligibleRecords.filter((r) => r.isFnfClosed) },
      avgTAT: { title: "F&F TAT Records", data: eligibleRecords.filter((r) => r.isFnfCompleted && r.fnfCompletedDate && r.gccInitiateDate) },
    };
    setKpiModalData(map[type]);
    setKpiCurrentPage(1);
    setKpiModalOpen(true);
  };

  const getFNFStatusLabel = (record: NDCRecord) => {
    if (record.isFnfCompleted) return "Completed";
    if (record.isFnfRevision) return "Revision Required";
    return "Open";
  };

  const getFNFStatusBadge = (record: NDCRecord) => {
    const label = getFNFStatusLabel(record);
    const colorMap: Record<string, string> = {
      "Closed": "bg-teal-50 text-teal-700 border-teal-200",
      "Completed": "bg-green-50 text-green-700 border-green-200",
      "Open": "bg-blue-50 text-blue-700 border-blue-200",
      "Revision Required": "bg-red-50 text-red-700 border-red-200",
    };
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-[4px] text-xs font-medium border ${colorMap[label] || ""}`}>
        {label}
      </span>
    );
  };

  const kpiCards = [
    { type: "total" as const, label: "Total F&F In Process", value: fnfStats.total, icon: FileText, color: "text-primary" },
    { type: "done" as const, label: "F&F Completed", value: fnfStats.done, icon: CheckCircle, color: "text-green-600" },
    { type: "closed" as const, label: "F&F Closed", value: fnfStats.closed, icon: CheckCircle, color: "text-teal-600" },
    { type: "open" as const, label: "F&F Open", value: fnfStats.open, icon: Clock, color: "text-blue-600" },
    { type: "revision" as const, label: "Revision Required", value: fnfStats.revision, icon: XCircle, color: "text-red-600" },
    { type: "avgTAT" as const, label: "F&F TAT (In Days)", value: fnfStats.avgTAT, icon: TrendingUp, color: "text-purple-600" },
  ];

  if (isLoading) return <LoadingScreen />;

  const handleDownloadPPT = async () => {
    const { createPPT, addImageSlide } = await import("../../utils/pptExport");
    const pptx = createPPT("FnF Management Dashboard");
    
    await addImageSlide(pptx, "F&F KPI Summary", "section-fnf-kpis");
    
    await pptx.writeFile({ fileName: "FnF_Management_Dashboard.pptx" });
  };

  return (
    <div className="p-8 space-y-6 bg-background min-h-full">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">F&amp;F Document Management</h1>
          <p className="text-muted-foreground mt-2">Full &amp; Final Settlement Processing</p>
        </div>
        <PPTDownloadButton onDownload={handleDownloadPPT} />
      </div>

      {/* KPI Cards */}
      <div id="section-fnf-kpis" className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
        {kpiCards.map(({ type, label, value, icon: Icon, color }) => (
          <div
            key={type}
            onClick={() => handleKPIClick(type)}
            className="bg-card rounded-[4px] p-5 border border-border cursor-pointer hover:scale-105 transition-transform duration-200 h-[110px] flex flex-col justify-between"
          >
            <div className="flex items-start justify-between gap-2">
              <span className="text-sm text-muted-foreground leading-tight">{label}</span>
              <Icon className={`w-5 h-5 flex-shrink-0 ${color}`} />
            </div>
            <p className={`text-3xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-card rounded-[4px] p-6 border border-border">
        <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
          <Filter className="w-5 h-5" />
          Filters
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">F&amp;F Status Filter</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full px-3 py-2 border border-border rounded-[4px] bg-input-background focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">All statuses</option>
              <option value="Closed">Closed</option>
              <option value="Done">Completed</option>
              <option value="Open">Open</option>
              <option value="Revision Required">Revision Required</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">Search Employee / Name</label>
            <input
              type="text"
              placeholder="Name or person number"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-3 py-2 border border-border rounded-[4px] bg-input-background focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
        </div>
      </div>

      {/* F&F Records Table */}
      <div id="section-fnf-table" className="bg-card rounded-[4px] border border-border overflow-hidden">
        <div className="p-6 border-b border-border flex items-center justify-between">
          <h2 className="text-xl font-bold">F&amp;F Records Table</h2>
          <button
            onClick={() => {
              const mappedData = filteredData.map(r => ({
                "Person number": r.personNumber,
                "Employee name": r.employeeName,
                "Department": r.department,
                "Last working date": r.lastWorkingDate,
                "F&F status": getFNFStatusLabel(r),
                "Doc count": r.fnfDocumentCount,
                "F&F completed date": r.fnfCompletedDate,
              }));
              exportToExcel(mappedData, "FNF_Records");
            }}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-[4px] hover:bg-primary/90 transition-colors"
          >
            <Download className="w-4 h-4" />
            Export to Excel
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Person number</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Employee name</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Department</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Last working date</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">F&amp;F status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-card divide-y divide-border">
              {paginatedData.map((record) => (
                <tr key={record.id} className="hover:bg-muted/50">
                  <td className="px-4 py-3 text-sm font-medium">{record.personNumber}</td>
                  <td className="px-4 py-3 text-sm">{record.employeeName}</td>
                  <td className="px-4 py-3 text-sm">{record.department}</td>
                  <td className="px-4 py-3 text-sm">{record.lastWorkingDate}</td>
                  <td className="px-4 py-3 text-sm">{getFNFStatusBadge(record)}</td>
                  <td className="px-4 py-3 text-sm">
                    <div className="flex gap-2 items-center">
                      <button
                        onClick={() => handleDocumentView(record)}
                        className="p-2 rounded-[4px] bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors"
                        title="View document"
                      >
                        <FileText className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => { setSelectedRecord(record); setActionDialogOpen(true); }}
                        className="p-2 rounded-[4px] bg-green-50 text-green-600 hover:bg-green-100 transition-colors"
                        title="Confirm F&F status"
                      >
                        <CheckSquare className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => { setMailRecord(record); setMailEmailTo(""); setMailDialogOpen(true); }}
                        className="p-2 rounded-[4px] bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
                        title="Send email"
                      >
                        <Mail className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {filteredData.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">No F&amp;F records found</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        
        {filteredData.length > 0 && (
          <div className="px-6 py-4 border-t border-border flex items-center justify-between">
            <div className="text-sm text-muted-foreground">
              Showing {startIndex + 1} to {Math.min(startIndex + itemsPerPage, filteredData.length)} of{" "}
              {filteredData.length} records
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                disabled={currentPage === 1}
                className="p-2 rounded-[4px] border border-border hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-sm text-foreground">
                Page {currentPage} of {totalPages}
              </span>
              <button
                onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                disabled={currentPage === totalPages}
                className="p-2 rounded-[4px] border border-border hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* KPI Full-Screen Modal */}
      <FullScreenModal
        open={kpiModalOpen}
        onClose={() => setKpiModalOpen(false)}
        title={kpiModalData.title}
        headerActions={
          <button
            onClick={() => {
              const mappedData = kpiModalData.data.map(r => ({
                "Person number": r.personNumber,
                "Name": r.employeeName,
                "Department": r.department,
                "Last working date": r.lastWorkingDate,
                "NDC stage": r.ndcStage,
                "F&F status": getFNFStatusLabel(r)
              }));
              exportToExcel(mappedData, kpiModalData.title || "KPI_Records");
            }}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-[4px] hover:bg-primary/90 transition-colors"
          >
            <Download className="w-4 h-4" />
            Export to Excel
          </button>
        }
      >
        <div className="flex flex-col flex-1 overflow-hidden p-4">
          <div className="bg-card rounded-[4px] border border-border flex flex-col flex-1 overflow-hidden">
            <div className="p-3 border-b border-border bg-muted/50 shrink-0">
              <span className="text-sm font-semibold text-foreground">
                Detailed records ({kpiModalData.data.length} records)
              </span>
            </div>
            <div className="overflow-x-auto overflow-y-auto flex-1">
              <table className="w-full text-sm">
                <thead className="bg-muted sticky top-0 z-10">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Person number</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Name</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Department</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Last working date</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">NDC stage</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">F&amp;F status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border bg-card">
                  {kpiPaginatedData.map((record) => (
                    <tr key={record.id} className="hover:bg-muted/50">
                      <td className="px-4 py-3 whitespace-nowrap">{record.personNumber}</td>
                      <td className="px-4 py-3 whitespace-nowrap">{record.employeeName}</td>
                      <td className="px-4 py-3">{record.department}</td>
                      <td className="px-4 py-3 whitespace-nowrap">{record.lastWorkingDate}</td>
                      <td className="px-4 py-3 whitespace-nowrap">{record.ndcStage}</td>
                      <td className="px-4 py-3">{getFNFStatusBadge(record)}</td>
                    </tr>
                  ))}
                  {kpiModalData.data.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">No records found</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            
            {kpiModalData.data.length > 0 && (
              <div className="px-6 py-4 border-t border-border flex items-center justify-between bg-card">
                <div className="text-sm text-muted-foreground">
                  Showing {kpiStartIndex + 1} to {Math.min(kpiStartIndex + itemsPerPage, kpiModalData.data.length)} of{" "}
                  {kpiModalData.data.length} records
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setKpiCurrentPage(Math.max(1, kpiCurrentPage - 1))}
                    disabled={kpiCurrentPage === 1}
                    className="p-2 rounded-[4px] border border-border hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="text-sm text-foreground">
                    Page {kpiCurrentPage} of {kpiTotalPages}
                  </span>
                  <button
                    onClick={() => setKpiCurrentPage(Math.min(kpiTotalPages, kpiCurrentPage + 1))}
                    disabled={kpiCurrentPage === kpiTotalPages}
                    className="p-2 rounded-[4px] border border-border hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </FullScreenModal>

      {/* Confirmation Dialog */}
      <Dialog open={actionDialogOpen} onOpenChange={setActionDialogOpen}>
        <DialogContent className="max-w-md p-6">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold text-foreground">F&amp;F document confirmation</DialogTitle>
          </DialogHeader>
          {selectedRecord && (
            <div className="space-y-6 pt-4">
              <div className="bg-[#f8fafc] border border-slate-200 p-5 rounded-[6px] space-y-1.5">
                <p className="text-sm text-slate-600">
                  Employee: <span className="font-semibold text-slate-900">{selectedRecord.employeeName}</span>
                </p>
                <p className="text-sm text-slate-500">
                  Person number: <span className="text-slate-700">{selectedRecord.personNumber}</span>
                </p>
                <p className="text-sm text-slate-500">
                  Department: <span className="text-slate-700">{selectedRecord.department}</span>
                </p>
              </div>
              
              <p className="text-base text-slate-900">
                Is the F&amp;F document ready to be processed?
              </p>
              
              <div className="flex gap-4">
                <button
                  onClick={() => handleAction(selectedRecord, "closed")}
                  className="flex-1 px-4 py-3 bg-[#00a651] text-white rounded-[6px] hover:bg-[#008f45] transition-colors flex items-center justify-center gap-2 font-semibold text-sm shadow-sm"
                >
                  <CheckCircle className="w-5 h-5 shrink-0" />
                  Closed
                </button>
                <button
                  onClick={() => handleAction(selectedRecord, "revision")}
                  className="flex-1 px-4 py-3 bg-[#e30613] text-white rounded-[6px] hover:bg-[#c2050f] transition-colors flex items-center justify-center gap-2 font-semibold text-sm shadow-sm"
                >
                  <XCircle className="w-5 h-5 shrink-0" />
                  Needs revision
                </button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Mail Dialog */}
      <Dialog open={mailDialogOpen} onOpenChange={setMailDialogOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Send email</DialogTitle>
          </DialogHeader>
          <div className="p-4 space-y-4">
            {mailRecord && (
              <p className="text-sm text-muted-foreground">
                <strong>Employee Name:</strong> <span className="font-medium text-foreground">{mailRecord.employeeName}</span>
              </p>
            )}
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                Email ID <span className="text-red-500">*</span>
              </label>
              <input
                type="email"
                value={mailEmailTo}
                onChange={(e) => setMailEmailTo(e.target.value)}
                placeholder="Enter email address"
                className="w-full px-3 py-2 border border-border rounded-[4px] bg-input-background focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => {
                  if (!mailRecord) return;
                  if (!mailEmailTo) {
                    toast.error("Please enter an email address");
                    return;
                  }
                  const toastId = toast.loading(`Sending F&F details email to ${mailEmailTo}...`);
                  axios.post("/api/v1/send-fnf-email", {
                    email: mailEmailTo,
                    record_id: parseInt(mailRecord.id)
                  })
                  .then(() => {
                    toast.dismiss(toastId);
                    toast.success(`Email sent successfully to ${mailEmailTo}`);
                    setMailDialogOpen(false);
                    setMailRecord(null);
                    setMailEmailTo("");
                  })
                  .catch((err) => {
                    toast.dismiss(toastId);
                    const errMsg = err.response?.data?.detail || err.message || "Failed to send email";
                    toast.error(errMsg);
                  });
                }}
                className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-[4px] hover:bg-primary/90 transition-colors flex items-center justify-center gap-2"
              >
                <Send className="w-4 h-4" />
                Send
              </button>
              <button
                onClick={() => { setMailDialogOpen(false); setMailRecord(null); setMailEmailTo(""); }}
                className="px-4 py-2 bg-muted text-foreground rounded-[4px] hover:bg-muted/80 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
