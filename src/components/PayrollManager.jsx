import { useState, useEffect } from 'react';
import { getEmployees, getCompany, getPayrolls, savePayroll } from '../utils/storage';
import { useCompany } from '../context/CompanyContext';
import PayrollList from './PayrollList';
import PayrollEditor from './PayrollEditor';

export default function PayrollManager() {
  const { activeCompanyId } = useCompany();
  const [editing, setEditing]     = useState(null);
  const [employees, setEmployees] = useState([]);
  const [company, setCompany]     = useState(null);
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([getEmployees(activeCompanyId), getCompany(activeCompanyId)]).then(([emps, co]) => {
      setEmployees(emps);
      setCompany(co);
      setLoading(false);
    });
  }, [activeCompanyId]); // Re-load when the active branch changes

  const handleEdit = async (payroll) => {
    // Refresh employees/company in case they changed
    const [emps, co] = await Promise.all([getEmployees(activeCompanyId), getCompany(activeCompanyId)]);
    setEmployees(emps);
    setCompany(co);
    setEditing(payroll);
  };

  const handleSave = async (payroll) => {
    await savePayroll(payroll);
    setEditing(payroll);
  };

  const handleBack = () => {
    setEditing(null);
  };

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>
        Loading payroll data…
      </div>
    );
  }

  if (editing) {
    return (
      <PayrollEditor
        payroll={editing}
        employees={employees}
        company={company}
        onSave={handleSave}
        onBack={handleBack}
      />
    );
  }

  return <PayrollList onEdit={handleEdit} />;
}
