import { useState, useMemo, useEffect } from "react";
import axios from "axios";
import { NDCRecord } from "../../types";
import { exportToExcel } from "../../utils/excelExport";
import { PPTDownloadButton } from "../../components/common/PPTDownloadButton";
import { FullScreenModal } from "../../components/common/FullScreenModal";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../../components/ui/dialog";
import { FileText, Download, Filter, CheckCircle, XCircle, Clock, Send, CheckSquare, Mail, TrendingUp } from "lucide-react";

export function FNFManagement() {
  const [mockNDCData, setMockNDCData] = useState<NDCRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = () => {
    axios.get("/api/v1/ndc-records").then((res) => {
      setMockNDCData(res.data);
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

  const filteredData = useMemo(() => {
    let filtered = mockNDCData;
    if (statusFilter) filtered = filtered.filter((r) => r.fnfStatus === statusFilter);
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (r) => r.employeeName.toLowerCase().includes(query) || r.personNumber.toLowerCase().includes(query)
      );
    }
    return filtered;
  }, [mockNDCData, statusFilter, searchQuery]);

  const fnfStats = useMemo(() => {
    const total = mockNDCData.length;
    const done = mockNDCData.filter((r) => r.fnfStatus === "Done" || r.fnfStatus === "Completed").length;
    const open = mockNDCData.filter((r) => r.fnfStatus === "Open").length;
    const revision = mockNDCData.filter((r) => r.fnfStatus === "Revision Required").length;
    const closed = mockNDCData.filter((r) => r.ndcCompletedDate).length;

    const closedRecords = mockNDCData.filter((r) => r.ndcCompletedDate && r.lastWorkingDate);
    const avgTAT = closedRecords.length > 0
      ? Math.round(
          closedRecords.reduce((sum, r) => {
            const end = new Date(r.ndcCompletedDate);
            const start = new Date(r.lastWorkingDate);
            return sum + Math.abs((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
          }, 0) / closedRecords.length
        )
      : 0;

    return { total, done, open, revision, closed, avgTAT };
  }, [mockNDCData]);

  const handleAction = (record: NDCRecord, action: "yes" | "no") => {
    const newStatus = action === "yes" ? "Done" : "Revision Required";
    axios.put(`/api/v1/ndc-records/${record.id}`, {
      fnfStatus: newStatus
    }).then(() => {
      fetchData();
      alert(`F&F status updated to ${newStatus} for ${record.employeeName} (${record.personNumber})`);
    });
    setActionDialogOpen(false);
    setSelectedRecord(null);
  };

  const handleDocumentView = (record: NDCRecord) => {
    if (record.fnfDocument) {
      alert(`Opening document: ${record.fnfDocument}`);
    } else {
      alert("No document available for this employee");
    }
  };

  const handleKPIClick = (type: "total" | "done" | "open" | "revision" | "closed" | "avgTAT") => {
    const map: Record<string, { title: string; data: NDCRecord[] }> = {
      total: { title: "Total F&F In Process", data: mockNDCData },
      done: { title: "F&F Completed", data: mockNDCData.filter((r) => r.fnfStatus === "Done" || r.fnfStatus === "Completed") },
      open: { title: "F&F Open", data: mockNDCData.filter((r) => r.fnfStatus === "Open") },
      revision: { title: "Revision Required", data: mockNDCData.filter((r) => r.fnfStatus === "Revision Required") },
      closed: { title: "F&F Closed", data: mockNDCData.filter((r) => r.ndcCompletedDate) },
      avgTAT: { title: "F&F TAT Records", data: mockNDCData.filter((r) => r.ndcCompletedDate && r.lastWorkingDate) },
    };
    setKpiModalData(map[type]);
    setKpiModalOpen(true);
  };

  const getFNFStatusLabel = (status: string) => {
    if (status === "Done" || status === "Completed") return "Completed";
    return status;
  };

  const getFNFStatusBadge = (status: string) => {
    if (!status) return <span className="text-muted-foreground">Not started</span>;
    const label = getFNFStatusLabel(status);
    const colorMap: Record<string, string> = {
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

  if (isLoading) return <div className="p-8 text-center">Loading...</div>;

  const handleDownloadPPT = async () => {
    const { createPPT, addImageSlide } = await import("../../utils/pptExport");
    const pptx = createPPT("FnF Management Dashboard");
    
    await addImageSlide(pptx, "F&F KPI Summary", "section-fnf-kpis");
    
    // const headers = ["Person Number", "Name", "Department", "Last Working Date", "F&F Status", "Delay Days"];
    // const rows = filteredData.map(r => {
    //    const delayDays = r.fnfStatus !== "Done" ? Math.max(0, Math.ceil((new Date().getTime() - new Date(r.lastWorkingDate).getTime()) / (1000 * 60 * 60 * 24))) : 0;
    //    return [
    //       r.personNumber,
    //       r.employeeName,
    //       r.department,
    //       r.lastWorkingDate,
    //       r.fnfStatus || "Pending",
    //       delayDays + " days"
    //    ];
    // });
    // 
    // addTableSlide(pptx, "F&F Records Table", headers, rows);
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
            onClick={() => exportToExcel(filteredData, "FNF_Records")}
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
              {filteredData.map((record) => (
                <tr key={record.id} className="hover:bg-muted/50">
                  <td className="px-4 py-3 text-sm font-medium">{record.personNumber}</td>
                  <td className="px-4 py-3 text-sm">{record.employeeName}</td>
                  <td className="px-4 py-3 text-sm">{record.department}</td>
                  <td className="px-4 py-3 text-sm">{record.lastWorkingDate}</td>
                  <td className="px-4 py-3 text-sm">{getFNFStatusBadge(record.fnfStatus)}</td>
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
      </div>

      {/* KPI Full-Screen Modal */}
      <FullScreenModal
        open={kpiModalOpen}
        onClose={() => setKpiModalOpen(false)}
        title={kpiModalData.title}
        headerActions={
          <button
            onClick={() => exportToExcel(kpiModalData.data, kpiModalData.title || "KPI_Records")}
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
                  {kpiModalData.data.map((record) => (
                    <tr key={record.id} className="hover:bg-muted/50">
                      <td className="px-4 py-3 whitespace-nowrap">{record.personNumber}</td>
                      <td className="px-4 py-3 whitespace-nowrap">{record.employeeName}</td>
                      <td className="px-4 py-3">{record.department}</td>
                      <td className="px-4 py-3 whitespace-nowrap">{record.lastWorkingDate}</td>
                      <td className="px-4 py-3 whitespace-nowrap">{record.ndcStage}</td>
                      <td className="px-4 py-3">{getFNFStatusBadge(record.fnfStatus)}</td>
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
          </div>
        </div>
      </FullScreenModal>

      {/* Confirmation Dialog */}
      <Dialog open={actionDialogOpen} onOpenChange={setActionDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>F&amp;F document confirmation</DialogTitle>
          </DialogHeader>
          {selectedRecord && (
            <div className="p-4 space-y-4">
              <div className="bg-muted p-4 rounded-[4px]">
                <p className="text-sm font-medium">Employee: {selectedRecord.employeeName}</p>
                <p className="text-sm text-muted-foreground">Person number: {selectedRecord.personNumber}</p>
                <p className="text-sm text-muted-foreground">Department: {selectedRecord.department}</p>
              </div>
              <p className="text-sm">Is the F&amp;F document ready to be processed?</p>
              <div className="flex gap-3">
                <button
                  onClick={() => handleAction(selectedRecord, "yes")}
                  className="flex-1 px-4 py-2 bg-green-600 text-white rounded-[4px] hover:bg-green-700 transition-colors flex items-center justify-center gap-2"
                >
                  <CheckCircle className="w-4 h-4" />
                  Closed
                </button>
                <button
                  onClick={() => handleAction(selectedRecord, "no")}
                  className="flex-1 px-4 py-2 bg-red-600 text-white rounded-[4px] hover:bg-red-700 transition-colors flex items-center justify-center gap-2"
                >
                  <XCircle className="w-4 h-4" />
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
                To: <span className="font-medium text-foreground">{mailRecord.employeeName}</span>
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
                  if (!mailEmailTo) { alert("Please enter an email address"); return; }
                  alert(`Email sent to ${mailEmailTo}`);
                  setMailDialogOpen(false);
                  setMailRecord(null);
                  setMailEmailTo("");
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
