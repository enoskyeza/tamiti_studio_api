"""
SACCO Account Views
Handles SACCO financial account management endpoints
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


class SaccoAccountViewSet(viewsets.ViewSet):
    """
    ViewSet for SACCO Account management
    Handles creation, retrieval, and updates of SACCO financial accounts
    """
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Get SACCO account for current user's SACCO"""
        from saccos.models import SaccoAccount
        from saccos.serializers_account import SaccoAccountSerializer
        
        if not hasattr(request.user, 'sacco_membership'):
            return Response({'error': 'Not a SACCO member'}, status=status.HTTP_400_BAD_REQUEST)
        
        sacco = request.user.sacco_membership.sacco
        
        try:
            account = SaccoAccount.objects.get(sacco=sacco)
            serializer = SaccoAccountSerializer(account)
            return Response(serializer.data)
        except SaccoAccount.DoesNotExist:
            return Response({'exists': False}, status=status.HTTP_404_NOT_FOUND)
    
    def create(self, request):
        """Create SACCO account"""
        from saccos.services.sacco_account_service import SaccoAccountService
        from saccos.serializers_account import CreateSaccoAccountSerializer, SaccoAccountSerializer
        
        if not hasattr(request.user, 'sacco_membership'):
            return Response({'error': 'Not a SACCO member'}, status=status.HTTP_400_BAD_REQUEST)
        
        sacco = request.user.sacco_membership.sacco
        
        # Check if account already exists
        from saccos.models import SaccoAccount
        if SaccoAccount.objects.filter(sacco=sacco).exists():
            return Response(
                {'error': 'SACCO account already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = CreateSaccoAccountSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        account_details = serializer.validated_data
        sacco_account = SaccoAccountService.get_or_create_sacco_account(
            sacco=sacco,
            account_details=account_details
        )
        
        response_serializer = SaccoAccountSerializer(sacco_account)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    def partial_update(self, request, pk=None):
        """Update SACCO account details"""
        from saccos.services.sacco_account_service import SaccoAccountService
        from saccos.models import SaccoAccount
        from saccos.serializers_account import UpdateSaccoAccountSerializer, SaccoAccountSerializer
        
        if not hasattr(request.user, 'sacco_membership'):
            return Response({'error': 'Not a SACCO member'}, status=status.HTTP_400_BAD_REQUEST)
        
        sacco = request.user.sacco_membership.sacco
        
        try:
            sacco_account = SaccoAccount.objects.get(sacco=sacco)
        except SaccoAccount.DoesNotExist:
            return Response({'error': 'SACCO account not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = UpdateSaccoAccountSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        updated_account = SaccoAccountService.update_account_details(
            sacco_account=sacco_account,
            **serializer.validated_data
        )
        
        response_serializer = SaccoAccountSerializer(updated_account)
        return Response(response_serializer.data)
    
    @action(detail=False, methods=['get'])
    def transactions(self, request):
        """Get SACCO account transactions"""
        from saccos.models import SaccoAccount
        from saccos.services.sacco_account_service import SaccoAccountService
        from saccos.serializers_account import SaccoAccountTransactionSerializer
        
        if not hasattr(request.user, 'sacco_membership'):
            return Response({'error': 'Not a SACCO member'}, status=status.HTTP_400_BAD_REQUEST)
        
        sacco = request.user.sacco_membership.sacco
        
        try:
            sacco_account = SaccoAccount.objects.get(sacco=sacco)
        except SaccoAccount.DoesNotExist:
            return Response({'error': 'SACCO account not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get filter parameters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        category = request.query_params.get('category')
        
        transactions = SaccoAccountService.get_transactions(
            sacco_account=sacco_account,
            start_date=start_date,
            end_date=end_date,
            category=category
        )
        
        serializer = SaccoAccountTransactionSerializer(transactions, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get SACCO account summary"""
        from saccos.models import SaccoAccount
        from saccos.services.sacco_account_service import SaccoAccountService
        from saccos.serializers_account import SaccoAccountSummarySerializer
        
        if not hasattr(request.user, 'sacco_membership'):
            return Response({'error': 'Not a SACCO member'}, status=status.HTTP_400_BAD_REQUEST)
        
        sacco = request.user.sacco_membership.sacco
        
        try:
            sacco_account = SaccoAccount.objects.get(sacco=sacco)
        except SaccoAccount.DoesNotExist:
            return Response({'error': 'SACCO account not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get filter parameters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        summary = SaccoAccountService.get_account_summary(
            sacco_account=sacco_account,
            start_date=start_date,
            end_date=end_date
        )
        
        serializer = SaccoAccountSummarySerializer(summary)
        return Response(serializer.data)
